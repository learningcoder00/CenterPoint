package com.centerpoint.viz.service;

import com.centerpoint.viz.dto.JobAnnotationMarker;
import com.centerpoint.viz.dto.JobAnnotationResponse;
import com.centerpoint.viz.model.Job;
import com.centerpoint.viz.dto.JobReviewResponse;
import com.centerpoint.viz.dto.ReviewRequest;
import com.centerpoint.viz.repository.JobRepository;
import com.centerpoint.viz.repository.JobReviewRepository;
import com.centerpoint.viz.repository.JobStarRepository;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.stream.Collectors;

@Service
public class JobService {

    private static final Set<String> ALLOWED_REVIEW = Set.of("unreviewed", "has_issue", "no_issue");

    private final JobRepository jobRepo;
    private final JobReviewRepository jobReviewRepo;
    private final JobStarRepository jobStarRepo;
    private final ClipService clipService;
    private final JobExecutor jobExecutor;

    public JobService(
        JobRepository jobRepo,
        JobReviewRepository jobReviewRepo,
        JobStarRepository jobStarRepo,
        ClipService clipService,
        JobExecutor jobExecutor
    ) {
        this.jobRepo = jobRepo;
        this.jobReviewRepo = jobReviewRepo;
        this.jobStarRepo = jobStarRepo;
        this.clipService = clipService;
        this.jobExecutor = jobExecutor;
    }

    /** Result of {@link #submitOrReuse}: a job plus a flag indicating reuse vs new. */
    public record SubmitResult(Job job, boolean reused) {}

    public Job createAndSubmit(
        String clipId,
        String config,
        String checkpoint,
        String configB,
        String checkpointB,
        String visualizationMode
    ) throws IOException {
        if (!clipService.exists(clipId)) {
            throw new IllegalArgumentException("Unknown clip_id: " + clipId);
        }
        String safeConfigB = configB == null ? "" : configB;
        String safeCheckpointB = checkpointB == null ? "" : checkpointB;
        int total = clipService.getFrameCount(clipId);
        String jobId = jobRepo.create(
            clipId, config, checkpoint, safeConfigB, safeCheckpointB, visualizationMode, total
        );
        jobExecutor.submit(jobId, config, checkpoint, safeConfigB, safeCheckpointB, visualizationMode);

        Job j = new Job();
        j.setJobId(jobId);
        j.setClipId(clipId);
        j.setConfig(config);
        j.setCheckpoint(checkpoint);
        j.setConfigB(safeConfigB);
        j.setCheckpointB(safeCheckpointB);
        j.setVisualizationMode(visualizationMode);
        j.setStatus("pending");
        return j;
    }

    /**
     * Reuse the latest completed job with identical parameters when {@code allowReuse}
     * is true; otherwise (or if no match exists) create+submit a new job.
     */
    public SubmitResult submitOrReuse(
        String clipId,
        String config,
        String checkpoint,
        String configB,
        String checkpointB,
        String visualizationMode,
        boolean allowReuse
    ) throws IOException {
        if (allowReuse) {
            Optional<Job> reusable = jobRepo.findReusableCompletedJob(
                clipId, config, checkpoint, configB, checkpointB, visualizationMode
            );
            if (reusable.isPresent()) {
                return new SubmitResult(reusable.get(), true);
            }
        }
        Job j = createAndSubmit(clipId, config, checkpoint, configB, checkpointB, visualizationMode);
        return new SubmitResult(j, false);
    }

    public List<Job> listJobs() throws IOException {
        List<Job> jobs = jobRepo.findAll();
        Map<String, Map<String, Object>> meta = clipService.getClipMeta();
        Map<String, String> reviewByJob = jobReviewRepo.findAllStatusByJobId();
        Set<String> starredJobs = jobStarRepo.findAllStarredJobIds();
        for (Job j : jobs) {
            Map<String, Object> m = meta.getOrDefault(j.getClipId(), Collections.emptyMap());
            j.setThumbnailPath((String) m.getOrDefault("thumbnail_path", ""));
            j.setFrameCount((Integer) m.getOrDefault("frame_count", 0));
            j.setReviewStatus(reviewByJob.getOrDefault(j.getJobId(), "unreviewed"));
            j.setStarred(starredJobs.contains(j.getJobId()));
            applyStaleFlag(j, meta);
        }
        return jobs;
    }

    private static void applyStaleFlag(Job j, Map<String, Map<String, Object>> meta) {
        List<String> reasons = new ArrayList<>();
        if (!meta.containsKey(j.getClipId())) {
            reasons.add("clip not in active dataset");
        }
        if ("completed".equals(j.getStatus())) {
            String mp4 = j.getMp4Path();
            if (mp4 == null || mp4.isBlank()) {
                reasons.add("mp4 path missing");
            } else if (!Files.exists(Path.of(mp4))) {
                reasons.add("mp4 file missing on disk");
            }
        }
        if (reasons.isEmpty()) {
            j.setStale(false);
            j.setStaleReason("");
        } else {
            j.setStale(true);
            j.setStaleReason(String.join("; ", reasons));
        }
    }

    public record BulkDeleteResult(int deleted, int notFound, int failed, List<String> errors) {}

    /**
     * Delete every job whose id is in {@code jobIds}, swallowing per-job errors so a
     * single bad row doesn't abort the batch. Returns counts for UI feedback.
     */
    public BulkDeleteResult bulkDelete(Collection<String> jobIds, Path jobsDir) {
        int deleted = 0;
        int notFound = 0;
        int failed = 0;
        List<String> errors = new ArrayList<>();
        Set<String> seen = new LinkedHashSet<>(jobIds);
        for (String id : seen) {
            if (id == null || id.isBlank()) {
                continue;
            }
            try {
                if (deleteJob(id, jobsDir)) {
                    deleted++;
                } else {
                    notFound++;
                }
            } catch (Exception e) {
                failed++;
                errors.add(id + ": " + e.getMessage());
            }
        }
        return new BulkDeleteResult(deleted, notFound, failed, errors);
    }

    public void starJob(String jobId) {
        if (jobRepo.findById(jobId).isEmpty()) {
            throw new IllegalArgumentException("Job not found: " + jobId);
        }
        jobStarRepo.star(jobId);
    }

    public boolean unstarJob(String jobId) {
        if (jobRepo.findById(jobId).isEmpty()) {
            return false;
        }
        return jobStarRepo.unstar(jobId);
    }

    public Optional<JobReviewResponse> getJobReview(String jobId) {
        if (jobRepo.findById(jobId).isEmpty()) return Optional.empty();
        return Optional.of(
            jobReviewRepo.findByJobId(jobId).orElseGet(() -> emptyReview(jobId))
        );
    }

    public Optional<JobReviewResponse> setJobReview(String jobId, ReviewRequest body) {
        if (jobRepo.findById(jobId).isEmpty()) return Optional.empty();
        String status = body.getReviewStatus() == null ? "unreviewed" : body.getReviewStatus().trim();
        if (!ALLOWED_REVIEW.contains(status)) {
            throw new IllegalArgumentException(
                "Invalid review_status. Use one of: unreviewed, has_issue, no_issue."
            );
        }
        String note = body.getNote() == null ? "" : body.getNote();
        return Optional.of(jobReviewRepo.upsert(jobId, status, note));
    }

    private static JobReviewResponse emptyReview(String jobId) {
        JobReviewResponse r = new JobReviewResponse();
        r.setJobId(jobId);
        r.setReviewStatus("unreviewed");
        r.setReviewerNote("");
        r.setUpdatedAt(0);
        return r;
    }

    public Optional<Job> getJob(String jobId) {
        return jobRepo.findById(jobId);
    }

    public Optional<JobAnnotationResponse> getJobAnnotations(String jobId) {
        if (jobRepo.findById(jobId).isEmpty()) return Optional.empty();
        return Optional.of(jobRepo.findAnnotations(jobId).orElseGet(() -> jobRepo.emptyAnnotations(jobId)));
    }

    public Optional<JobAnnotationResponse> saveJobAnnotations(String jobId, String note, List<JobAnnotationMarker> markers) {
        if (jobRepo.findById(jobId).isEmpty()) return Optional.empty();

        List<JobAnnotationMarker> normalized = (markers == null ? Collections.<JobAnnotationMarker>emptyList() : markers)
            .stream()
            .filter(Objects::nonNull)
            .filter(marker -> marker.getId() != null && !marker.getId().isBlank())
            .map(marker -> {
                JobAnnotationMarker copy = new JobAnnotationMarker();
                copy.setId(marker.getId().trim());
                copy.setTimeSec(Math.max(0.0, marker.getTimeSec()));
                copy.setType((marker.getType() == null || marker.getType().isBlank()) ? "bug" : marker.getType().trim());
                copy.setSide(normalizeSide(marker.getSide()));
                return copy;
            })
            .sorted(Comparator.comparingDouble(JobAnnotationMarker::getTimeSec))
            .collect(Collectors.toList());

        return Optional.of(jobRepo.upsertAnnotations(jobId, note == null ? "" : note, normalized));
    }

    private static String normalizeSide(String raw) {
        if (raw == null) return "both";
        String s = raw.trim().toLowerCase(java.util.Locale.ROOT);
        return switch (s) {
            case "a", "b", "both" -> s;
            default -> "both";
        };
    }

    /** Stop a queued/running job. Wipes partial frames+mp4, marks status='cancelled'. */
    public JobExecutor.CancelResult cancelJob(String jobId) {
        return jobExecutor.cancel(jobId);
    }

    public boolean deleteJob(String jobId, Path jobsDir) throws IOException {
        Optional<Job> jobOpt = jobRepo.findById(jobId);
        if (jobOpt.isEmpty()) return false;
        Path jobDir = jobsDir.resolve(jobId);
        if (Files.exists(jobDir)) {
            deleteRecursively(jobDir);
        }
        jobRepo.deleteAnnotations(jobId);
        jobReviewRepo.deleteByJobId(jobId);
        jobStarRepo.deleteByJobId(jobId);
        jobRepo.delete(jobId);
        return true;
    }

    private void deleteRecursively(Path path) throws IOException {
        if (Files.isDirectory(path)) {
            try (var stream = Files.list(path)) {
                for (Path child : stream.toList()) {
                    deleteRecursively(child);
                }
            }
        }
        Files.deleteIfExists(path);
    }
}
