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

    public JobExecutor(AppProperties props, JobRepository jobRepo, ClipService clipService) {
        this.props = props;
        this.jobRepo = jobRepo;
        this.clipService = clipService;
    }

    @PostConstruct
    public void recoverInterruptedJobs() {
        int recovered = jobRepo.failInterruptedJobsOnStartup();
        if (recovered > 0) {
            log.warn("Marked {} interrupted jobs as failed during startup recovery", recovered);
        }
    }

    public void submit(String jobId, String config, String checkpoint) {
        pool.submit(() -> {
            try {
                executeJob(jobId, config, checkpoint);
            } catch (Exception e) {
                log.error("Unexpected error in job {}", jobId, e);
                jobRepo.updateFailed(jobId, "Internal error: " + e.getMessage());
            }
        });
    }

    private void executeJob(String jobId, String config, String checkpoint) throws Exception {
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
        visCmd.add("--output-dir"); visCmd.add(framesDir.toString());
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
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(ffProc.getInputStream()))) {
            String line;
            while ((line = reader.readLine()) != null) {
                logLines.add(line + "\n");
            }
        }

        int ffExit = ffProc.waitFor();
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
