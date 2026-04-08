package com.centerpoint.viz.controller;

import com.centerpoint.viz.config.AppProperties;
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

        if (!notEmpty(config)) {
            return ResponseEntity.status(400).body(Map.of("detail",
                "No config specified. Pass 'config' in body or start server with --app.config."));
        }
        if (!notEmpty(checkpoint)) {
            return ResponseEntity.status(400).body(Map.of("detail",
                "No checkpoint specified. Pass 'checkpoint' in body or start server with --app.checkpoint."));
        }

        List<Map<String, Object>> created = new ArrayList<>();
        for (String clipId : body.getClipIds()) {
            try {
                Job job = jobService.createAndSubmit(clipId, config, checkpoint);
                Map<String, Object> m = new LinkedHashMap<>();
                m.put("job_id", job.getJobId());
                m.put("clip_id", job.getClipId());
                m.put("status", job.getStatus());
                created.add(m);
            } catch (IllegalArgumentException e) {
                return ResponseEntity.status(400).body(Map.of("detail", e.getMessage()));
            } catch (IOException e) {
                return ResponseEntity.status(500).body(Map.of("detail", e.getMessage()));
            }
        }
        return ResponseEntity.status(202).body(Map.of("jobs", created));
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

    @DeleteMapping("/{jobId}")
    public ResponseEntity<?> deleteJob(@PathVariable String jobId) {
        try {
            Path jobsDir = props.projectRootPath().resolve(props.getJobsDir());
            boolean ok = jobService.deleteJob(jobId, jobsDir);
            if (!ok) return ResponseEntity.status(404).body(Map.of("detail", "Job not found"));
            return ResponseEntity.ok(Map.of("deleted", jobId));
        } catch (IOException e) {
            return ResponseEntity.status(500).body(Map.of("detail", e.getMessage()));
        }
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
