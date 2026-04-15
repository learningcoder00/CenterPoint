package com.centerpoint.viz.service;

import com.centerpoint.viz.dto.JobAnnotationMarker;
import com.centerpoint.viz.dto.JobAnnotationResponse;
import com.centerpoint.viz.model.Job;
import com.centerpoint.viz.repository.JobRepository;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.stream.Collectors;

@Service
public class JobService {

    private final JobRepository jobRepo;
    private final ClipService clipService;
    private final JobExecutor jobExecutor;

    public JobService(JobRepository jobRepo, ClipService clipService, JobExecutor jobExecutor) {
        this.jobRepo = jobRepo;
        this.clipService = clipService;
        this.jobExecutor = jobExecutor;
    }

    public Job createAndSubmit(String clipId, String config, String checkpoint) throws IOException {
        if (!clipService.exists(clipId)) {
            throw new IllegalArgumentException("Unknown clip_id: " + clipId);
        }
        int total = clipService.getFrameCount(clipId);
        String jobId = jobRepo.create(clipId, config, checkpoint, total);
        jobExecutor.submit(jobId, config, checkpoint);

        Job j = new Job();
        j.setJobId(jobId);
        j.setClipId(clipId);
        j.setStatus("pending");
        return j;
    }

    public List<Job> listJobs() throws IOException {
        List<Job> jobs = jobRepo.findAll();
        Map<String, Map<String, Object>> meta = clipService.getClipMeta();
        for (Job j : jobs) {
            Map<String, Object> m = meta.getOrDefault(j.getClipId(), Collections.emptyMap());
            j.setThumbnailPath((String) m.getOrDefault("thumbnail_path", ""));
            j.setFrameCount((Integer) m.getOrDefault("frame_count", 0));
        }
        return jobs;
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
                return copy;
            })
            .sorted(Comparator.comparingDouble(JobAnnotationMarker::getTimeSec))
            .collect(Collectors.toList());

        return Optional.of(jobRepo.upsertAnnotations(jobId, note == null ? "" : note, normalized));
    }

    public boolean deleteJob(String jobId, Path jobsDir) throws IOException {
        Optional<Job> jobOpt = jobRepo.findById(jobId);
        if (jobOpt.isEmpty()) return false;
        Path jobDir = jobsDir.resolve(jobId);
        if (Files.exists(jobDir)) {
            deleteRecursively(jobDir);
        }
        jobRepo.deleteAnnotations(jobId);
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
