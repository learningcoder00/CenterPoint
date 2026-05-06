package com.centerpoint.viz.repository;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.HashSet;
import java.util.List;
import java.util.Set;

@Repository
public class JobStarRepository {

    private final JdbcTemplate jdbc;

    public JobStarRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public void star(String jobId) {
        double now = System.currentTimeMillis() / 1000.0;
        jdbc.update(
            "INSERT INTO job_stars (job_id, starred_at) VALUES (?,?) " +
            "ON CONFLICT(job_id) DO UPDATE SET starred_at=excluded.starred_at",
            jobId, now
        );
    }

    public boolean unstar(String jobId) {
        return jdbc.update("DELETE FROM job_stars WHERE job_id=?", jobId) > 0;
    }

    public Set<String> findAllStarredJobIds() {
        List<String> ids = jdbc.query(
            "SELECT job_id FROM job_stars",
            (rs, rowNum) -> rs.getString("job_id")
        );
        return new HashSet<>(ids);
    }

    public void deleteByJobId(String jobId) {
        jdbc.update("DELETE FROM job_stars WHERE job_id=?", jobId);
    }
}
