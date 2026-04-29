package com.centerpoint.viz.repository;

import com.centerpoint.viz.dto.JobAnnotationMarker;
import com.centerpoint.viz.dto.JobAnnotationResponse;
import com.centerpoint.viz.model.Job;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import jakarta.annotation.PostConstruct;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public class JobRepository {

    private final JdbcTemplate jdbc;
    private final ObjectMapper objectMapper;

    public JobRepository(JdbcTemplate jdbc, ObjectMapper objectMapper) {
        this.jdbc = jdbc;
        this.objectMapper = objectMapper;
    }

    @PostConstruct
    public void ensureSchema() {
        Integer tableCount = jdbc.queryForObject(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='jobs'",
            Integer.class
        );
        if (tableCount == null || tableCount == 0) {
            return;
        }
        boolean hasVisualizationMode = jdbc.queryForList("PRAGMA table_info(jobs)")
            .stream()
            .anyMatch(row -> "visualization_mode".equals(row.get("name")));
        if (!hasVisualizationMode) {
            jdbc.execute("ALTER TABLE jobs ADD COLUMN visualization_mode TEXT NOT NULL DEFAULT 'bev_cameras'");
        }
    }

    private static final RowMapper<Job> ROW_MAPPER = (rs, rowNum) -> mapRow(rs);

    private static Job mapRow(ResultSet rs) throws SQLException {
        Job j = new Job();
        j.setJobId(rs.getString("job_id"));
        j.setClipId(rs.getString("clip_id"));
        j.setConfig(rs.getString("config"));
        j.setCheckpoint(rs.getString("checkpoint"));
        j.setVisualizationMode(rs.getString("visualization_mode"));
        j.setStatus(rs.getString("status"));
        j.setProgress(rs.getInt("progress"));
        j.setTotal(rs.getInt("total"));
        j.setMp4Path(rs.getString("mp4_path"));
        j.setLog(rs.getString("log"));
        j.setCreatedAt(rs.getDouble("created_at"));
        j.setUpdatedAt(rs.getDouble("updated_at"));
        return j;
    }

    public String create(String clipId, String config, String checkpoint, String visualizationMode, int total) {
        String jobId = UUID.randomUUID().toString().replace("-", "");
        double now = System.currentTimeMillis() / 1000.0;
        jdbc.update(
            "INSERT INTO jobs (job_id, clip_id, config, checkpoint, visualization_mode, status, total, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            jobId, clipId, config, checkpoint, visualizationMode, "pending", total, now, now
        );
        return jobId;
    }

    public Optional<Job> findById(String jobId) {
        List<Job> rows = jdbc.query(
            "SELECT * FROM jobs WHERE job_id=?", ROW_MAPPER, jobId
        );
        return rows.isEmpty() ? Optional.empty() : Optional.of(rows.get(0));
    }

    public List<Job> findAll() {
        return jdbc.query("SELECT * FROM jobs ORDER BY created_at DESC", ROW_MAPPER);
    }

    public boolean delete(String jobId) {
        int rows = jdbc.update("DELETE FROM jobs WHERE job_id=?", jobId);
        return rows > 0;
    }

    /**
     * Atomic compare-and-swap: pending -> running.
     * Returns true if this caller won the race.
     */
    public boolean claimRunning(String jobId) {
        double now = System.currentTimeMillis() / 1000.0;
        int rows = jdbc.update(
            "UPDATE jobs SET status='running', updated_at=? WHERE job_id=? AND status='pending'",
            now, jobId
        );
        return rows > 0;
    }

    public void updateStatus(String jobId, String status) {
        double now = System.currentTimeMillis() / 1000.0;
        jdbc.update(
            "UPDATE jobs SET status=?, updated_at=? WHERE job_id=?",
            status, now, jobId
        );
    }

    public void updateProgress(String jobId, int progress, String log) {
        double now = System.currentTimeMillis() / 1000.0;
        jdbc.update(
            "UPDATE jobs SET progress=?, log=?, updated_at=? WHERE job_id=?",
            progress, log, now, jobId
        );
    }

    public void updateCompleted(String jobId, String mp4Path, int frames, String log) {
        double now = System.currentTimeMillis() / 1000.0;
        jdbc.update(
            "UPDATE jobs SET status='completed', mp4_path=?, progress=?, total=?, log=?, updated_at=? WHERE job_id=?",
            mp4Path, frames, frames, log, now, jobId
        );
    }

    public void updateFailed(String jobId, String log) {
        double now = System.currentTimeMillis() / 1000.0;
        jdbc.update(
            "UPDATE jobs SET status='failed', log=?, updated_at=? WHERE job_id=?",
            log, now, jobId
        );
    }

    public void updateStitching(String jobId, String log) {
        double now = System.currentTimeMillis() / 1000.0;
        jdbc.update(
            "UPDATE jobs SET status='stitching', log=?, updated_at=? WHERE job_id=?",
            log, now, jobId
        );
    }

    public int failInterruptedJobsOnStartup() {
        double now = System.currentTimeMillis() / 1000.0;
        String recoveryNote =
            "\n[recovery] Process interrupted: server restarted while this job was in progress.";
        return jdbc.update(
            "UPDATE jobs " +
            "SET status='failed', " +
            "    log=COALESCE(log, '') || ?, " +
            "    updated_at=? " +
            "WHERE status IN ('pending', 'running', 'stitching')",
            recoveryNote, now
        );
    }

    public Optional<JobAnnotationResponse> findAnnotations(String jobId) {
        List<JobAnnotationResponse> rows = jdbc.query(
            "SELECT job_id, note, markers_json, created_at, updated_at FROM job_video_annotations WHERE job_id=?",
            (rs, rowNum) -> mapAnnotations(rs),
            jobId
        );
        return rows.isEmpty() ? Optional.empty() : Optional.of(rows.get(0));
    }

    public JobAnnotationResponse upsertAnnotations(String jobId, String note, List<JobAnnotationMarker> markers) {
        double now = System.currentTimeMillis() / 1000.0;
        String safeNote = note == null ? "" : note;
        List<JobAnnotationMarker> safeMarkers = markers == null ? new ArrayList<>() : markers;
        String markersJson = writeMarkersJson(safeMarkers);

        jdbc.update(
            "INSERT INTO job_video_annotations (job_id, note, markers_json, created_at, updated_at) " +
            "VALUES (?,?,?,?,?) " +
            "ON CONFLICT(job_id) DO UPDATE SET note=excluded.note, markers_json=excluded.markers_json, updated_at=excluded.updated_at",
            jobId, safeNote, markersJson, now, now
        );

        return findAnnotations(jobId).orElseGet(() -> emptyAnnotations(jobId));
    }

    public void deleteAnnotations(String jobId) {
        jdbc.update("DELETE FROM job_video_annotations WHERE job_id=?", jobId);
    }

    private JobAnnotationResponse mapAnnotations(ResultSet rs) throws SQLException {
        JobAnnotationResponse response = new JobAnnotationResponse();
        response.setJobId(rs.getString("job_id"));
        response.setNote(rs.getString("note"));
        response.setMarkers(readMarkersJson(rs.getString("markers_json")));
        response.setCreatedAt(rs.getDouble("created_at"));
        response.setUpdatedAt(rs.getDouble("updated_at"));
        return response;
    }

    private String writeMarkersJson(List<JobAnnotationMarker> markers) {
        try {
            return objectMapper.writeValueAsString(markers);
        } catch (Exception e) {
            throw new IllegalStateException("Failed to serialize annotation markers", e);
        }
    }

    private List<JobAnnotationMarker> readMarkersJson(String json) {
        try {
            if (json == null || json.isBlank()) return new ArrayList<>();
            return objectMapper.readValue(json, new TypeReference<List<JobAnnotationMarker>>() {});
        } catch (Exception e) {
            throw new IllegalStateException("Failed to deserialize annotation markers", e);
        }
    }

    public JobAnnotationResponse emptyAnnotations(String jobId) {
        JobAnnotationResponse response = new JobAnnotationResponse();
        response.setJobId(jobId);
        response.setNote("");
        response.setMarkers(new ArrayList<>());
        response.setCreatedAt(0);
        response.setUpdatedAt(0);
        return response;
    }
}
