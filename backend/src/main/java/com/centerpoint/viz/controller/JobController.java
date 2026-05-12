package com.centerpoint.viz.controller;

import com.centerpoint.viz.config.AppProperties;
import com.centerpoint.viz.dto.JobAnnotationRequest;
import com.centerpoint.viz.dto.ReviewRequest;
import com.centerpoint.viz.dto.SubmitJobsRequest;
import com.centerpoint.viz.model.Job;
import com.centerpoint.viz.service.JobService;
import org.springframework.core.io.FileSystemResource;
import org.springframework.core.io.Resource;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

@RestController
@RequestMapping("/api/jobs")
public class JobController {

    private final JobService jobService;
    private final AppProperties props;

    public JobController(JobService jobService, AppProperties props) {
        this.jobService = jobService;
        this.props = props;
    }

    @PostMapping
    public ResponseEntity<?> submitJobs(@RequestBody SubmitJobsRequest body) {
        String config = notEmpty(body.getConfig()) ? body.getConfig() : props.getConfig();
        String checkpoint = notEmpty(body.getCheckpoint()) ? body.getCheckpoint() : props.getCheckpoint();
        String visualizationMode = notEmpty(body.getVisualizationMode()) ? body.getVisualizationMode() : "bev_cameras";
        String configB = body.getConfigB();
        String checkpointB = body.getCheckpointB();

        if (!notEmpty(config)) {
            return ResponseEntity.status(400).body(Map.of("detail",
                "No config specified. Pass 'config' in body or start server with --app.config."));
        }
        if (!notEmpty(checkpoint)) {
            return ResponseEntity.status(400).body(Map.of("detail",
                "No checkpoint specified. Pass 'checkpoint' in body or start server with --app.checkpoint."));
        }
        if (!Set.of("bev_cameras", "forward_points", "bev_compare").contains(visualizationMode)) {
            return ResponseEntity.status(400).body(Map.of("detail",
                "Invalid visualization_mode. Use 'bev_cameras', 'forward_points', or 'bev_compare'."));
        }
        if ("bev_compare".equals(visualizationMode)) {
            if (!notEmpty(configB) || !notEmpty(checkpointB)) {
                return ResponseEntity.status(400).body(Map.of("detail",
                    "bev_compare mode requires both 'config_b' and 'checkpoint_b'."));
            }
        } else {
            // ignore B-side fields for non-compare modes to keep the row clean
            configB = "";
            checkpointB = "";
        }

        boolean allowReuse = body.getReuseCompleted() == null || body.getReuseCompleted();

        List<Map<String, Object>> created = new ArrayList<>();
        int reusedCount = 0;
        int newCount = 0;
        for (String clipId : body.getClipIds()) {
            try {
                JobService.SubmitResult result = jobService.submitOrReuse(
                    clipId, config, checkpoint, configB, checkpointB, visualizationMode, allowReuse
                );
                Job job = result.job();
                Map<String, Object> m = new LinkedHashMap<>();
                m.put("job_id", job.getJobId());
                m.put("clip_id", job.getClipId());
                m.put("status", job.getStatus());
                m.put("visualization_mode", job.getVisualizationMode());
                m.put("reused", result.reused());
                if ("bev_compare".equals(job.getVisualizationMode())) {
                    m.put("config_b", job.getConfigB());
                    m.put("checkpoint_b", job.getCheckpointB());
                }
                created.add(m);
                if (result.reused()) reusedCount++;
                else newCount++;
            } catch (IllegalArgumentException e) {
                return ResponseEntity.status(400).body(Map.of("detail", e.getMessage()));
            } catch (IOException e) {
                return ResponseEntity.status(500).body(Map.of("detail", e.getMessage()));
            }
        }
        return ResponseEntity.status(202).body(Map.of(
            "jobs", created,
            "reused_count", reusedCount,
            "new_count", newCount
        ));
    }

    @GetMapping
    public ResponseEntity<?> listJobs() {
        try {
            List<Job> jobs = jobService.listJobs();
            return ResponseEntity.ok(Map.of("jobs", jobs));
        } catch (IOException e) {
            return ResponseEntity.status(500).body(Map.of("detail", e.getMessage()));
        }
    }

    @GetMapping("/{jobId}")
    public ResponseEntity<?> getJob(@PathVariable String jobId) {
        return jobService.getJob(jobId)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.status(404).build());
    }

    @GetMapping("/{jobId}/annotations")
    public ResponseEntity<?> getJobAnnotations(@PathVariable String jobId) {
        var annotations = jobService.getJobAnnotations(jobId);
        if (annotations.isEmpty()) {
            return ResponseEntity.status(404).body(Map.of("detail", "Job not found"));
        }
        return ResponseEntity.ok(annotations.get());
    }

    @PutMapping("/{jobId}/annotations")
    public ResponseEntity<?> saveJobAnnotations(
        @PathVariable String jobId,
        @RequestBody JobAnnotationRequest body
    ) {
        var annotations = jobService.saveJobAnnotations(jobId, body.getNote(), body.getMarkers());
        if (annotations.isEmpty()) {
            return ResponseEntity.status(404).body(Map.of("detail", "Job not found"));
        }
        return ResponseEntity.ok(annotations.get());
    }

    @GetMapping("/{jobId}/review")
    public ResponseEntity<?> getJobReview(@PathVariable String jobId) {
        var review = jobService.getJobReview(jobId);
        if (review.isEmpty()) {
            return ResponseEntity.status(404).body(Map.of("detail", "Job not found"));
        }
        return ResponseEntity.ok(review.get());
    }

    @PutMapping("/{jobId}/review")
    public ResponseEntity<?> putJobReview(@PathVariable String jobId, @RequestBody ReviewRequest body) {
        try {
            var saved = jobService.setJobReview(jobId, body);
            if (saved.isEmpty()) {
                return ResponseEntity.status(404).body(Map.of("detail", "Job not found"));
            }
            return ResponseEntity.ok(saved.get());
        } catch (IllegalArgumentException e) {
            return ResponseEntity.status(400).body(Map.of("detail", e.getMessage()));
        }
    }

    @PostMapping("/{jobId}/star")
    public ResponseEntity<?> starJob(@PathVariable String jobId) {
        try {
            jobService.starJob(jobId);
            return ResponseEntity.ok(Map.of("job_id", jobId, "starred", true));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.status(404).body(Map.of("detail", e.getMessage()));
        }
    }

    @DeleteMapping("/{jobId}/star")
    public ResponseEntity<?> unstarJob(@PathVariable String jobId) {
        try {
            boolean ok = jobService.unstarJob(jobId);
            if (!ok) {
                return ResponseEntity.status(404).body(Map.of("detail", "Job not found or not starred"));
            }
            return ResponseEntity.ok(Map.of("job_id", jobId, "starred", false));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.status(404).body(Map.of("detail", e.getMessage()));
        }
    }

    /**
     * Stop a pending/running job. Kills the active subprocess (if any) and wipes
     * partial frames so a fresh submit starts clean. Final status='cancelled'.
     */
    @PostMapping("/{jobId}/cancel")
    public ResponseEntity<?> cancelJob(@PathVariable String jobId) {
        var result = jobService.cancelJob(jobId);
        return switch (result) {
            case NOT_FOUND -> ResponseEntity.status(404).body(Map.of("detail", "Job not found"));
            case ALREADY_TERMINAL -> ResponseEntity.status(409).body(Map.of(
                "detail", "Job is already in a terminal state (completed/failed/cancelled)."
            ));
            case DEQUEUED -> ResponseEntity.ok(Map.of(
                "cancelled", jobId, "kind", "dequeued",
                "message", "Removed from queue before execution."
            ));
            case KILLED_RUNNING -> ResponseEntity.ok(Map.of(
                "cancelled", jobId, "kind", "killed_running",
                "message", "Subprocess terminated and partial frames cleaned up."
            ));
        };
    }

    @DeleteMapping("/{jobId}")
    public ResponseEntity<?> deleteJob(@PathVariable String jobId) {
        try {
            Path jobsDir = props.projectRootPath().resolve(props.getJobsDir());
            boolean ok = jobService.deleteJob(jobId, jobsDir);
            if (!ok) return ResponseEntity.status(404).body(Map.of("detail", "Job not found"));
            return ResponseEntity.ok(Map.of("deleted", jobId));
        } catch (IllegalStateException e) {
            return ResponseEntity.status(409).body(Map.of("detail", e.getMessage()));
        } catch (IOException e) {
            return ResponseEntity.status(500).body(Map.of("detail", e.getMessage()));
        }
    }

    /**
     * Bulk-delete endpoint used by the Results page batch toolbar.
     *
     * <p>Accepted bodies:
     * <ul>
     *   <li>{@code { "job_ids": ["id1", "id2", ...] }}</li>
     *   <li>{@code { "filter": "all" | "stale" | "failed" | "completed" }}</li>
     * </ul>
     *
     * <p>Returns counts so the UI can show a friendly summary. Errors on individual
     * rows are collected, not aborted.
     */
    @PostMapping("/bulk-delete")
    public ResponseEntity<?> bulkDelete(@RequestBody Map<String, Object> body) {
        try {
            Path jobsDir = props.projectRootPath().resolve(props.getJobsDir());
            List<String> ids = collectBulkDeleteIds(body);
            if (ids.isEmpty()) {
                return ResponseEntity.status(400).body(Map.of(
                    "detail", "No job ids resolved. Provide 'job_ids' (array) or 'filter' (all|stale|failed|completed)."
                ));
            }
            JobService.BulkDeleteResult result = jobService.bulkDelete(ids, jobsDir);
            Map<String, Object> resp = new LinkedHashMap<>();
            resp.put("deleted", result.deleted());
            resp.put("not_found", result.notFound());
            resp.put("failed", result.failed());
            resp.put("requested", ids.size());
            if (!result.errors().isEmpty()) {
                resp.put("errors", result.errors());
            }
            return ResponseEntity.ok(resp);
        } catch (IOException e) {
            return ResponseEntity.status(500).body(Map.of("detail", e.getMessage()));
        }
    }

    /** Resolve the effective job_id list from either an explicit array or a server-side filter. */
    private List<String> collectBulkDeleteIds(Map<String, Object> body) throws IOException {
        if (body == null) return List.of();
        Object raw = body.getOrDefault("job_ids", body.get("jobIds"));
        if (raw instanceof Collection<?> c) {
            List<String> ids = new ArrayList<>();
            for (Object o : c) {
                if (o == null) continue;
                String s = String.valueOf(o).trim();
                if (!s.isEmpty()) ids.add(s);
            }
            return ids;
        }
        Object filter = body.getOrDefault("filter", body.get("filter_status"));
        if (filter == null) return List.of();
        String f = String.valueOf(filter).trim().toLowerCase(Locale.ROOT);
        List<Job> jobs = jobService.listJobs();
        return switch (f) {
            case "all" -> jobs.stream().map(Job::getJobId).toList();
            case "stale" -> jobs.stream().filter(Job::isStale).map(Job::getJobId).toList();
            case "failed", "completed", "pending", "running", "stitching", "cancelled" ->
                jobs.stream().filter(j -> f.equals(j.getStatus())).map(Job::getJobId).toList();
            default -> List.of();
        };
    }

    @GetMapping("/{jobId}/video")
    public ResponseEntity<Resource> streamVideo(
        @PathVariable String jobId,
        @RequestHeader HttpHeaders headers
    ) {
        Optional<Job> jobOpt = jobService.getJob(jobId);
        if (jobOpt.isEmpty()) {
            return ResponseEntity.status(404).build();
        }
        Job job = jobOpt.get();
        if (!"completed".equals(job.getStatus()) || job.getMp4Path() == null) {
            return ResponseEntity.status(409).build();
        }
        Path mp4 = Path.of(job.getMp4Path());
        if (!Files.exists(mp4)) {
            return ResponseEntity.status(404).build();
        }

        Resource resource = new FileSystemResource(mp4);
        long fileLen;
        try {
            fileLen = Files.size(mp4);
        } catch (IOException e) {
            return ResponseEntity.status(500).build();
        }

        // Support Range requests so the browser video player can seek
        List<HttpRange> ranges = headers.getRange();
        if (!ranges.isEmpty()) {
            HttpRange range = ranges.get(0);
            long start = range.getRangeStart(fileLen);
            long end = range.getRangeEnd(fileLen);
            long length = end - start + 1;

            return ResponseEntity.status(206)
                .header(HttpHeaders.CONTENT_TYPE, "video/mp4")
                .header(HttpHeaders.ACCEPT_RANGES, "bytes")
                .header(HttpHeaders.CONTENT_RANGE, "bytes " + start + "-" + end + "/" + fileLen)
                .header(HttpHeaders.CONTENT_LENGTH, String.valueOf(length))
                .body(new RangeResource(resource, start, length));
        }

        return ResponseEntity.ok()
            .header(HttpHeaders.CONTENT_TYPE, "video/mp4")
            .header(HttpHeaders.ACCEPT_RANGES, "bytes")
            .header(HttpHeaders.CONTENT_LENGTH, String.valueOf(fileLen))
            .body(resource);
    }

    private boolean notEmpty(String s) {
        return s != null && !s.isBlank();
    }

    // Inner helper: wraps a resource to return only the specified byte range
    static class RangeResource extends FileSystemResource {
        private final long offset;
        private final long length;

        RangeResource(Resource delegate, long offset, long length) {
            super(((FileSystemResource) delegate).getFile());
            this.offset = offset;
            this.length = length;
        }

        @Override
        public java.io.InputStream getInputStream() throws IOException {
            java.io.InputStream in = super.getInputStream();
            in.skip(offset);
            return new LimitedInputStream(in, length);
        }
    }

    static class LimitedInputStream extends java.io.FilterInputStream {
        private long remaining;

        LimitedInputStream(java.io.InputStream in, long limit) {
            super(in);
            this.remaining = limit;
        }

        @Override
        public int read() throws IOException {
            if (remaining <= 0) return -1;
            int b = super.read();
            if (b != -1) remaining--;
            return b;
        }

        @Override
        public int read(byte[] buf, int off, int len) throws IOException {
            if (remaining <= 0) return -1;
            int toRead = (int) Math.min(len, remaining);
            int read = super.read(buf, off, toRead);
            if (read > 0) remaining -= read;
            return read;
        }
    }
}
