package com.centerpoint.viz.service;

import com.centerpoint.viz.model.Job;
import com.centerpoint.viz.repository.JobRepository;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;

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

    public boolean deleteJob(String jobId, Path jobsDir) throws IOException {
        Optional<Job> jobOpt = jobRepo.findById(jobId);
        if (jobOpt.isEmpty()) return false;
        Path jobDir = jobsDir.resolve(jobId);
        if (Files.exists(jobDir)) {
            deleteRecursively(jobDir);
        }
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
