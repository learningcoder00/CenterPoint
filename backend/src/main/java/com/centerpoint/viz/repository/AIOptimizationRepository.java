package com.centerpoint.viz.repository;

import com.centerpoint.viz.model.AIOptimization;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.List;
import java.util.Map;

@Repository
public class AIOptimizationRepository {

    private final JdbcTemplate jdbc;

    public AIOptimizationRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
        ensureClipIdColumn();
    }

    private static final RowMapper<AIOptimization> ROW_MAPPER = (rs, rowNum) -> mapRow(rs);

    private static AIOptimization mapRow(ResultSet rs) throws SQLException {
        AIOptimization ai = new AIOptimization();
        ai.setId(rs.getInt("id"));
        ai.setJobId(rs.getString("job_id"));
        ai.setClipId(rs.getString("clip_id"));
        ai.setDescription(rs.getString("description"));
        ai.setResponse(rs.getString("response"));
        ai.setCreatedAt(rs.getDouble("created_at"));
        return ai;
    }

    private void ensureClipIdColumn() {
        List<Map<String, Object>> columns = jdbc.queryForList("PRAGMA table_info(ai_optimizations)");
        boolean hasClipId = columns.stream().anyMatch(col -> "clip_id".equals(col.get("name")));
        if (!hasClipId) {
            jdbc.execute("ALTER TABLE ai_optimizations ADD COLUMN clip_id TEXT");
        }
        jdbc.update(
            "UPDATE ai_optimizations " +
            "SET clip_id = (SELECT clip_id FROM jobs WHERE jobs.job_id = ai_optimizations.job_id) " +
            "WHERE clip_id IS NULL"
        );
        jdbc.execute("CREATE INDEX IF NOT EXISTS idx_ai_optimizations_clip ON ai_optimizations(clip_id)");
    }

    public int create(String jobId, String clipId, String description, String response) {
        double now = System.currentTimeMillis() / 1000.0;
        return jdbc.update(
            "INSERT INTO ai_optimizations (job_id, clip_id, description, response, created_at) VALUES (?,?,?,?,?)",
            jobId, clipId, description, response, now
        );
    }

    public List<AIOptimization> findAll() {
        return jdbc.query("SELECT * FROM ai_optimizations ORDER BY created_at DESC", ROW_MAPPER);
    }

    public List<AIOptimization> findByJobId(String jobId) {
        return jdbc.query("SELECT * FROM ai_optimizations WHERE job_id=? ORDER BY created_at DESC", ROW_MAPPER, jobId);
    }

    public boolean delete(int id) {
        int rows = jdbc.update("DELETE FROM ai_optimizations WHERE id=?", id);
        return rows > 0;
    }
}