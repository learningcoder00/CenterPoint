package com.centerpoint.viz.service;

import com.centerpoint.viz.config.AppProperties;
import com.centerpoint.viz.repository.JobRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.stream.Collectors;

/**
 * Executes visualization jobs as background threads.
 * Uses a single-thread executor (mirrors Python's Semaphore(1)) so jobs run serially.
 */
@Service
public class JobExecutor {

    private static final Logger log = LoggerFactory.getLogger(JobExecutor.class);

    private final AppProperties props;
    private final JobRepository jobRepo;
    private final ClipService clipService;

    // Single-thread executor: one job at a time (same as Python asyncio.Semaphore(1))
    private final ExecutorService pool = Executors.newSingleThreadExecutor(
        r -> { Thread t = new Thread(r, "job-executor"); t.setDaemon(true); return t; }
    );

    // Track live work so that we can cancel pending Futures or kill running Processes
    // from a REST endpoint (POST /api/jobs/{id}/cancel).
    private final Map<String, Future<?>> jobFutures = new ConcurrentHashMap<>();
    private final Map<String, Process> runningProcesses = new ConcurrentHashMap<>();
    private final Set<String> cancelledJobs = ConcurrentHashMap.newKeySet();

    public JobExecutor(AppProperties props, JobRepository jobRepo, ClipService clipService) {
        this.props = props;
        this.jobRepo = jobRepo;
        this.clipService = clipService;
    }

    @PostConstruct
    public void recoverInterruptedJobs() {
        List<String> recovered = jobRepo.failInterruptedJobsOnStartup();
        if (recovered.isEmpty()) {
            log.info("Startup recovery: no interrupted jobs found.");
            return;
        }
        log.warn("Startup recovery: marked {} interrupted job(s) as failed: {}",
            recovered.size(), recovered);
        for (String jobId : recovered) {
            log.warn("  - job {} was pending/running/stitching when the server stopped — resubmit to rerun.", jobId);
        }
    }

    public void submit(
        String jobId,
        String config,
        String checkpoint,
        String configB,
        String checkpointB,
        String visualizationMode
    ) {
        Future<?> f = pool.submit(() -> {
            try {
                executeJob(jobId, config, checkpoint, configB, checkpointB, visualizationMode);
            } catch (Exception e) {
                log.error("Unexpected error in job {}", jobId, e);
                if (cancelledJobs.contains(jobId)) {
                    // Already marked cancelled by cancel(); don't overwrite with "failed".
                } else {
                    jobRepo.updateFailed(jobId, "Internal error: " + e.getMessage());
                }
            } finally {
                runningProcesses.remove(jobId);
                jobFutures.remove(jobId);
                cancelledJobs.remove(jobId);
            }
        });
        jobFutures.put(jobId, f);
    }

    /**
     * Cancel a pending or running job. Behaviour:
     * <ul>
     *   <li>{@code pending} → remove from the executor queue, mark cancelled.</li>
     *   <li>{@code running}/{@code stitching} → destroy the active subprocess
     *       (graceful first, then force after 3s), then wipe partial frames
     *       and stitched mp4 from the job directory so a re-submit starts clean.</li>
     *   <li>terminal states ({@code completed}/{@code failed}/{@code cancelled})
     *       → no-op, returns false.</li>
     * </ul>
     */
    public CancelResult cancel(String jobId) {
        var jobOpt = jobRepo.findById(jobId);
        if (jobOpt.isEmpty()) return CancelResult.NOT_FOUND;
        String status = jobOpt.get().getStatus();
        if (status == null) return CancelResult.NOT_FOUND;
        switch (status) {
            case "completed":
            case "failed":
            case "cancelled":
                return CancelResult.ALREADY_TERMINAL;
            default:
                break;
        }

        cancelledJobs.add(jobId);
        Future<?> f = jobFutures.get(jobId);
        Process p = runningProcesses.get(jobId);
        boolean killedSomething = false;

        if (p != null && p.isAlive()) {
            p.destroy();
            try {
                if (!p.waitFor(3, TimeUnit.SECONDS)) {
                    p.destroyForcibly();
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                p.destroyForcibly();
            }
            killedSomething = true;
        }
        if (f != null && !f.isDone()) {
            // Cancel without interrupting: the running thread is past readline() and
            // will exit on the next tick once the subprocess pipe closes.
            f.cancel(false);
            killedSomething = true;
        }

        // Best-effort cleanup of frames + mp4 + concat file
        try {
            Path jobsDir = props.projectRootPath().resolve(props.getJobsDir());
            Path jobDir = jobsDir.resolve(jobId);
            wipePartialOutputs(jobDir, jobOpt.get().getClipId());
        } catch (Exception cleanupErr) {
            log.warn("Job {} cancel: partial cleanup failed: {}", jobId, cleanupErr.getMessage());
        }

        String reason = "Cancelled by user at " + java.time.LocalTime.now()
            .truncatedTo(java.time.temporal.ChronoUnit.SECONDS);
        jobRepo.updateCancelled(jobId, reason);
        log.info("Job {} cancelled (killedSubprocess={}, was status={})", jobId, killedSomething, status);
        return killedSomething ? CancelResult.KILLED_RUNNING : CancelResult.DEQUEUED;
    }

    public enum CancelResult { NOT_FOUND, ALREADY_TERMINAL, DEQUEUED, KILLED_RUNNING }

    /** Delete partial frames/mp4/concat after a cancel so a resubmit starts clean. */
    private static void wipePartialOutputs(Path jobDir, String clipId) throws IOException {
        if (!Files.isDirectory(jobDir)) return;
        Path framesDir = jobDir.resolve("frames");
        if (Files.isDirectory(framesDir)) {
            try (var stream = Files.list(framesDir)) {
                stream.filter(p -> {
                    String n = p.getFileName().toString().toLowerCase();
                    return n.endsWith(".jpg") || n.endsWith(".jpeg") || n.endsWith(".png");
                }).forEach(p -> { try { Files.deleteIfExists(p); } catch (IOException ignored) {} });
            }
        }
        Path concat = jobDir.resolve("concat.txt");
        Files.deleteIfExists(concat);
        if (clipId != null && !clipId.isBlank()) {
            Files.deleteIfExists(jobDir.resolve(clipId + ".mp4"));
        }
    }

    private void executeJob(
        String jobId,
        String config,
        String checkpoint,
        String configB,
        String checkpointB,
        String visualizationMode
    ) throws Exception {
        // Atomic CAS: only proceed if still 'pending'
        if (!jobRepo.claimRunning(jobId)) {
            log.info("Job {} already claimed by another worker, skipping", jobId);
            return;
        }

        Path projectRoot = props.projectRootPath();
        Path jobsDir = projectRoot.resolve(props.getJobsDir());
        Path jobDir = jobsDir.resolve(jobId);
        Path framesDir = jobDir.resolve("frames");
        Files.createDirectories(framesDir);

        jobRepo.updateProgress(jobId, 0, "Starting inference...\n");

        // --- Step 1: visualize_results.py ---
        List<String> tokens;
        String clipId;
        try {
            var jobOpt = jobRepo.findById(jobId);
            if (jobOpt.isEmpty()) return;
            clipId = jobOpt.get().getClipId();
            tokens = clipService.getTokens(clipId);
        } catch (Exception e) {
            jobRepo.updateFailed(jobId, "Failed to load clip tokens: " + e.getMessage());
            return;
        }

        List<String> visCmd = new ArrayList<>();
        visCmd.add(props.getPythonExecutable());
        visCmd.add(projectRoot.resolve(props.getVisScript()).toString());
        visCmd.add("--config"); visCmd.add(config);
        visCmd.add("--checkpoint"); visCmd.add(checkpoint);
        visCmd.add("--visualization-mode"); visCmd.add(visualizationMode);
        if ("bev_compare".equals(visualizationMode)) {
            if (configB == null || configB.isBlank() || checkpointB == null || checkpointB.isBlank()) {
                jobRepo.updateFailed(jobId,
                    "bev_compare job missing config_b/checkpoint_b; cannot run side-B inference.");
                return;
            }
            visCmd.add("--config-b"); visCmd.add(configB);
            visCmd.add("--checkpoint-b"); visCmd.add(checkpointB);
        }
        visCmd.add("--output-dir"); visCmd.add(framesDir.toString());

        // Per-clip mini infos pkl cache (avoids the multi-hour full infos_val_*.pkl build
        // — see tools/visualize_results.py --mini-infos-cache). Shared across jobs so that
        // re-running the same clip is instant after the first call.
        Path miniCacheDir = projectRoot.resolve("work_dirs").resolve(".mini_infos_cache");
        try {
            Files.createDirectories(miniCacheDir);
        } catch (Exception ignore) {}
        visCmd.add("--mini-infos-cache"); visCmd.add(miniCacheDir.toString());

        visCmd.add("--tokens");
        visCmd.addAll(tokens);

        String cmdSummary = String.format("[inference] cmd: %s ... (%d tokens)\n",
            visCmd.subList(0, Math.min(6, visCmd.size())), tokens.size());
        List<String> logLines = new ArrayList<>();
        logLines.add(cmdSummary);

        // Set PYTHONPATH so det3d modules are importable
        Map<String, String> env = new HashMap<>(System.getenv());
        String existing = env.getOrDefault("PYTHONPATH", "");
        env.put("PYTHONPATH", projectRoot + (existing.isEmpty() ? "" : File.pathSeparator + existing));

        ProcessBuilder visPb = new ProcessBuilder(visCmd);
        visPb.directory(projectRoot.toFile());
        visPb.redirectErrorStream(true);
        visPb.environment().putAll(env);

        Process visProc = visPb.start();
        runningProcesses.put(jobId, visProc);
        int completedFrames = 0;

        try (BufferedReader reader = new BufferedReader(new InputStreamReader(visProc.getInputStream()))) {
            String line;
            while ((line = reader.readLine()) != null) {
                logLines.add(line + "\n");
                if (line.startsWith("  Saved:")) {
                    completedFrames++;
                    String logSnippet = tail(logLines, 200);
                    jobRepo.updateProgress(jobId, completedFrames, logSnippet);
                }
            }
        }

        int visExit = visProc.waitFor();
        runningProcesses.remove(jobId);
        if (cancelledJobs.contains(jobId)) {
            log.info("Job {} aborted after inference (user cancel).", jobId);
            return;
        }
        if (visExit != 0) {
            jobRepo.updateFailed(jobId, tail(logLines, 200));
            return;
        }

        // --- Step 2: ffmpeg ---
        List<Path> jpgFiles;
        try (var stream = Files.list(framesDir)) {
            jpgFiles = stream
                .filter(p -> p.toString().endsWith(".jpg"))
                .sorted()
                .collect(Collectors.toList());
        }

        if (jpgFiles.isEmpty()) {
            jobRepo.updateFailed(jobId, "No frames produced by visualize_results.py");
            return;
        }

        jobRepo.updateStitching(jobId, tail(logLines, 200));

        // Write concat list
        Path concatFile = jobDir.resolve("concat.txt");
        try (PrintWriter w = new PrintWriter(Files.newBufferedWriter(concatFile))) {
            for (Path jpg : jpgFiles) {
                w.println("file '" + jpg.toAbsolutePath() + "'");
                w.println("duration 0.5");
            }
        }

        Path mp4Path = jobDir.resolve(clipId + ".mp4");
        List<String> ffCmd = List.of(
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", concatFile.toString(),
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            mp4Path.toString()
        );

        logLines.add(String.format("\n[ffmpeg] stitching %d frames -> %s\n", jpgFiles.size(), mp4Path.getFileName()));

        ProcessBuilder ffPb = new ProcessBuilder(ffCmd);
        ffPb.directory(projectRoot.toFile());
        ffPb.redirectErrorStream(true);

        Process ffProc = ffPb.start();
        runningProcesses.put(jobId, ffProc);
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(ffProc.getInputStream()))) {
            String line;
            while ((line = reader.readLine()) != null) {
                logLines.add(line + "\n");
            }
        }

        int ffExit = ffProc.waitFor();
        runningProcesses.remove(jobId);
        if (cancelledJobs.contains(jobId)) {
            log.info("Job {} aborted during stitching (user cancel).", jobId);
            return;
        }
        if (ffExit != 0) {
            jobRepo.updateFailed(jobId, tail(logLines, 200));
            return;
        }

        jobRepo.updateCompleted(jobId, mp4Path.toString(), jpgFiles.size(), tail(logLines, 200));
        log.info("Job {} completed: {} frames -> {}", jobId, jpgFiles.size(), mp4Path);
    }

    private static String tail(List<String> lines, int n) {
        int from = Math.max(0, lines.size() - n);
        return String.join("", lines.subList(from, lines.size()));
    }

    @PreDestroy
    public void shutdown() {
        pool.shutdownNow();
    }
}
