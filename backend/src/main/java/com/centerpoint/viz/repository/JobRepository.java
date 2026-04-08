package com.centerpoint.viz.repository;

import com.centerpoint.viz.model.Job;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public class JobRepository {

    private final JdbcTemplate jdbc;

    public JobRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    private static final RowMapper<Job> ROW_MAPPER = (rs, rowNum) -> mapRow(rs);

    private static Job mapRow(ResultSet rs) throws SQLException {
        Job j = new Job();
        j.setJobId(rs.getString("job_id"));
        j.setClipId(rs.getString("clip_id"));
        j.setConfig(rs.getString("config"));
        j.setCheckpoint(rs.getString("checkpoint"));
        j.setStatus(rs.getString("status"));
        j.setProgress(rs.getInt("progress"));
        j.setTotal(rs.getInt("total"));
        j.setMp4Path(rs.getString("mp4_path"));
        j.setLog(rs.getString("log"));
        j.setCreatedAt(rs.getDouble("created_at"));
        j.setUpdatedAt(rs.getDouble("updated_at"));
        return j;
    }

    public String create(String clipId, String config, String checkpoint, int total) {
        String jobId = UUID.randomUUID().toString().replace("-", "");
        double now = System.currentTimeMillis() / 1000.0;
        jdbc.update(
            "INSERT INTO jobs (job_id, clip_id, config, checkpoint, status, total, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
            jobId, clipId, config, checkpoint, "pending", total, now, now
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
}
