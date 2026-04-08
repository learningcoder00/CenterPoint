package com.centerpoint.viz.repository;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Repository
public class TagRepository {

    private final JdbcTemplate jdbc;
    private final ObjectMapper mapper = new ObjectMapper();

    public TagRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public List<String> findByClipId(String clipId) {
        List<String> rows = jdbc.queryForList(
            "SELECT tags FROM tags WHERE clip_id=?", String.class, clipId
        );
        if (rows.isEmpty()) return Collections.emptyList();
        return parseTags(rows.get(0));
    }

    /**
     * Returns map of clipId -> tags for all clips.
     */
    public Map<String, List<String>> findAll() {
        return jdbc.queryForList("SELECT clip_id, tags FROM tags")
            .stream()
            .collect(Collectors.toMap(
                r -> (String) r.get("clip_id"),
                r -> parseTags((String) r.get("tags"))
            ));
    }

    public void upsert(String clipId, List<String> tags) {
        String json = toJson(tags);
        jdbc.update(
            "INSERT INTO tags(clip_id, tags) VALUES(?,?) ON CONFLICT(clip_id) DO UPDATE SET tags=excluded.tags",
            clipId, json
        );
    }

    private List<String> parseTags(String json) {
        try {
            return mapper.readValue(json, mapper.getTypeFactory().constructCollectionType(List.class, String.class));
        } catch (Exception e) {
            return Collections.emptyList();
        }
    }

    private String toJson(List<String> tags) {
        try {
            return mapper.writeValueAsString(tags);
        } catch (JsonProcessingException e) {
            return "[]";
        }
    }
}
