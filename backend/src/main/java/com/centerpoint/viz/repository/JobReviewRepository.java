package com.centerpoint.viz.repository;

import com.centerpoint.viz.dto.JobReviewResponse;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@Repository
public class JobReviewRepository {

    private final JdbcTemplate jdbc;

    public JobReviewRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public Optional<JobReviewResponse> findByJobId(String jobId) {
        List<JobReviewResponse> rows = jdbc.query(
            "SELECT job_id, review_status, reviewer_note, updated_at FROM job_reviews WHERE job_id=?",
            (rs, rowNum) -> {
                JobReviewResponse r = new JobReviewResponse();
                r.setJobId(rs.getString("job_id"));
                r.setReviewStatus(rs.getString("review_status"));
                r.setReviewerNote(rs.getString("reviewer_note"));
                r.setUpdatedAt(rs.getDouble("updated_at"));
                return r;
            },
            jobId
        );
        return rows.isEmpty() ? Optional.empty() : Optional.of(rows.get(0));
    }

    /**
     * All persisted reviews keyed by job_id (review_status only needed for list enrich;
     * use findByJobId for full row).
     */
    public Map<String, String> findAllStatusByJobId() {
        List<Map<String, Object>> rows = jdbc.queryForList(
            "SELECT job_id, review_status FROM job_reviews"
        );
        Map<String, String> out = new HashMap<>();
        for (Map<String, Object> row : rows) {
            out.put((String) row.get("job_id"), (String) row.get("review_status"));
        }
        return out;
    }

    public JobReviewResponse upsert(String jobId, String reviewStatus, String reviewerNote) {
        double now = System.currentTimeMillis() / 1000.0;
        String safeNote = reviewerNote == null ? "" : reviewerNote;
        jdbc.update(
            "INSERT INTO job_reviews (job_id, review_status, reviewer_note, updated_at) VALUES (?,?,?,?) " +
            "ON CONFLICT(job_id) DO UPDATE SET review_status=excluded.review_status, " +
            "reviewer_note=excluded.reviewer_note, updated_at=excluded.updated_at",
            jobId, reviewStatus, safeNote, now
        );
        return findByJobId(jobId).orElseThrow();
    }

    public void deleteByJobId(String jobId) {
        jdbc.update("DELETE FROM job_reviews WHERE job_id=?", jobId);
    }
}
