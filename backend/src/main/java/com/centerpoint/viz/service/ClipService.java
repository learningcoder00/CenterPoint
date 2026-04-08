package com.centerpoint.viz.service;

import com.centerpoint.viz.config.AppProperties;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

@Service
public class ClipService {

    private final AppProperties props;
    private final ObjectMapper mapper = new ObjectMapper();

    // Cache: clipId -> clip JsonNode (includes frames)
    private final Map<String, JsonNode> cache = new ConcurrentHashMap<>();
    private volatile boolean loaded = false;

    public ClipService(AppProperties props) {
        this.props = props;
    }

    public synchronized void ensureLoaded() throws IOException {
        if (loaded) return;
        reload();
    }

    public synchronized void reload() throws IOException {
        Path metaPath = props.projectRootPath().resolve(props.getClipsMeta());
        if (!Files.exists(metaPath)) {
            throw new IllegalStateException("clips_meta.json not found: " + metaPath);
        }
        JsonNode root = mapper.readTree(metaPath.toFile());
        JsonNode clips = root.get("clips");
        if (clips == null || !clips.isArray()) return;
        Map<String, JsonNode> newCache = new LinkedHashMap<>();
        for (JsonNode clip : clips) {
            newCache.put(clip.get("clip_id").asText(), clip);
        }
        cache.clear();
        cache.putAll(newCache);
        loaded = true;
    }

    /** Returns all clips in order, each as a JsonNode (without frames). */
    public List<JsonNode> listClips() throws IOException {
        ensureLoaded();
        List<JsonNode> result = new ArrayList<>();
        for (JsonNode clip : cache.values()) {
            ObjectNode copy = clip.deepCopy();
            copy.remove("frames");
            result.add(copy);
        }
        return result;
    }

    /** Returns a single clip with frames (full detail). */
    public Optional<JsonNode> getClip(String clipId) throws IOException {
        ensureLoaded();
        return Optional.ofNullable(cache.get(clipId));
    }

    /** Returns a simple map of clipId -> { thumbnail_path, frame_count } for job list enrichment. */
    public Map<String, Map<String, Object>> getClipMeta() throws IOException {
        ensureLoaded();
        Map<String, Map<String, Object>> result = new HashMap<>();
        for (Map.Entry<String, JsonNode> e : cache.entrySet()) {
            Map<String, Object> meta = new HashMap<>();
            JsonNode clip = e.getValue();
            meta.put("thumbnail_path", clip.has("thumbnail_path") ? clip.get("thumbnail_path").asText() : "");
            meta.put("frame_count", clip.has("frame_count") ? clip.get("frame_count").asInt() : 0);
            result.put(e.getKey(), meta);
        }
        return result;
    }

    /** Returns tokens list for a given clip (used when submitting a job). */
    public List<String> getTokens(String clipId) throws IOException {
        ensureLoaded();
        JsonNode clip = cache.get(clipId);
        if (clip == null) throw new IllegalArgumentException("Unknown clip_id: " + clipId);
        List<String> tokens = new ArrayList<>();
        JsonNode frames = clip.get("frames");
        if (frames != null && frames.isArray()) {
            for (JsonNode frame : frames) {
                tokens.add(frame.get("token").asText());
            }
        }
        return tokens;
    }

    public boolean exists(String clipId) throws IOException {
        ensureLoaded();
        return cache.containsKey(clipId);
    }

    public int getFrameCount(String clipId) throws IOException {
        ensureLoaded();
        JsonNode clip = cache.get(clipId);
        if (clip == null) return 0;
        return clip.has("frame_count") ? clip.get("frame_count").asInt() : 0;
    }
}
