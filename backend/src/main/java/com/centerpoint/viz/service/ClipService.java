package com.centerpoint.viz.service;

import com.centerpoint.viz.config.AppProperties;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import jakarta.annotation.PostConstruct;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

@Service
public class ClipService {

    private static final String ACTIVE_META_REL = "work_dirs/active_clips_meta.rel";
    private static final String CLIP_PREVIEW_DIR = "clip_preview";

    private final AppProperties props;
    private final ObjectMapper mapper = new ObjectMapper();

    private String activeClipsMetaRelative;

    private final Map<String, JsonNode> cache = new ConcurrentHashMap<>();
    private volatile boolean loaded = false;

    public ClipService(AppProperties props) {
        this.props = props;
        this.activeClipsMetaRelative = normalizeRelative(props.getClipsMeta());
    }

    private static String normalizeRelative(String rel) {
        return rel.replace('\\', '/');
    }

    @PostConstruct
    public void loadPersistedMetaChoice() {
        Path root = props.projectRootPath().normalize();
        Path persist = root.resolve(ACTIVE_META_REL);
        if (!Files.exists(persist)) return;
        try {
            String s = normalizeRelative(Files.readString(persist, StandardCharsets.UTF_8).trim());
            if (s.isEmpty()) return;
            Path candidate = root.resolve(s).normalize();
            if (!candidate.startsWith(root)) return;
            if (!Files.isRegularFile(candidate)) return;
            if (!isAllowedMetaPath(root, candidate)) return;
            this.activeClipsMetaRelative = s;
            loaded = false;
        } catch (IOException ignored) {
            // keep defaults from application.yml
        }
    }

    /** Paths allowed for clips_meta switching (under project root). */
    public static boolean isAllowedMetaPath(Path projectRoot, Path absoluteMetaFile) {
        Path root = projectRoot.normalize();
        Path file = absoluteMetaFile.normalize();
        if (!file.startsWith(root)) return false;
        Path rel = root.relativize(file);
        if (rel.getNameCount() < 2) return false;
        if (!CLIP_PREVIEW_DIR.equalsIgnoreCase(rel.getName(0).toString())) return false;
        String name = rel.getFileName().toString().toLowerCase(Locale.ROOT);
        return name.startsWith("clips_meta") && name.endsWith(".json");
    }

    public String getActiveClipsMetaRelative() {
        return activeClipsMetaRelative;
    }

    public synchronized void switchToRelative(String relativePath) throws IOException {
        Path root = props.projectRootPath().normalize();
        Path target = root.resolve(normalizeRelative(relativePath)).normalize();
        if (!target.startsWith(root)) {
            throw new IllegalArgumentException("Path escapes project root");
        }
        if (!Files.isRegularFile(target)) {
            throw new IllegalArgumentException("clips_meta file not found: " + relativePath);
        }
        if (!isAllowedMetaPath(root, target)) {
            throw new IllegalArgumentException("Only clip_preview/clips_meta*.json files are allowed");
        }
        String rel = normalizeRelative(root.relativize(target).toString());
        this.activeClipsMetaRelative = rel;
        Files.createDirectories(root.resolve("work_dirs"));
        Files.writeString(root.resolve(ACTIVE_META_REL), rel + "\n", StandardCharsets.UTF_8);
        loaded = false;
        reload();
    }

    private Path metaPath() {
        return props.projectRootPath().resolve(activeClipsMetaRelative).normalize();
    }

    public synchronized void ensureLoaded() throws IOException {
        if (loaded) return;
        reload();
    }

    public synchronized void reload() throws IOException {
        Path metaPath = metaPath();
        if (!Files.exists(metaPath)) {
            throw new IllegalStateException("clips_meta not found: " + metaPath);
        }
        JsonNode root = mapper.readTree(metaPath.toFile());
        JsonNode clips = root.get("clips");
        if (clips == null || !clips.isArray()) {
            cache.clear();
            loaded = true;
            return;
        }
        Map<String, JsonNode> newCache = new LinkedHashMap<>();
        for (JsonNode clip : clips) {
            newCache.put(clip.get("clip_id").asText(), clip);
        }
        cache.clear();
        cache.putAll(newCache);
        loaded = true;
    }

    /** Dataset label from loaded metadata (optional). */
    public Optional<String> getDatasetKey() throws IOException {
        ensureLoaded();
        JsonNode root = mapper.readTree(metaPath().toFile());
        if (root.hasNonNull("dataset_key")) {
            return Optional.of(root.get("dataset_key").asText());
        }
        return Optional.empty();
    }

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

    public Optional<JsonNode> getClip(String clipId) throws IOException {
        ensureLoaded();
        return Optional.ofNullable(cache.get(clipId));
    }

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
