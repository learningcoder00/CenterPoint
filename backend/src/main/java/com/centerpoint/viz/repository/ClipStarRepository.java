package com.centerpoint.viz.repository;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * Persistence for the {@code clip_stars} table (defined in schema.sql).
 * Mirrors {@link JobStarRepository} so the UI can keep a "difficult corner cases"
 * shortlist at the clip level.
 */
@Repository
public class ClipStarRepository {

    private final JdbcTemplate jdbc;

    public ClipStarRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public void star(String clipId) {
        double now = System.currentTimeMillis() / 1000.0;
        jdbc.update(
            "INSERT INTO clip_stars (clip_id, starred_at) VALUES (?,?) " +
            "ON CONFLICT(clip_id) DO UPDATE SET starred_at=excluded.starred_at",
            clipId, now
        );
    }

    public boolean unstar(String clipId) {
        return jdbc.update("DELETE FROM clip_stars WHERE clip_id=?", clipId) > 0;
    }

    public Set<String> findAllStarredClipIds() {
        List<String> ids = jdbc.query(
            "SELECT clip_id FROM clip_stars",
            (rs, rowNum) -> rs.getString("clip_id")
        );
        return new HashSet<>(ids);
    }
}
