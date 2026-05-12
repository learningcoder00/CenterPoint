package com.centerpoint.viz.controller;

import com.centerpoint.viz.config.AppProperties;
import com.centerpoint.viz.service.ClipService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.stream.Collectors;
import java.util.stream.Stream;

@RestController
@RequestMapping("/api/config")
public class ConfigController {

    private final AppProperties props;
    private final ClipService clipService;
    private final ObjectMapper mapper = new ObjectMapper();

    public ConfigController(AppProperties props, ClipService clipService) {
        this.props = props;
        this.clipService = clipService;
    }

    @GetMapping
    public Map<String, Object> getConfig() {
        Map<String, Object> resp = new LinkedHashMap<>();
        resp.put("config", props.getConfig());
        resp.put("checkpoint", props.getCheckpoint());
        resp.put("configs", discoverFiles("configs", List.of(".py")));
        resp.put("checkpoints", discoverFiles(List.of("work_dirs", "checkpoints", "weights"), List.of(".pth", ".pt", ".ckpt")));
        resp.put("clips_meta", props.projectRootPath().resolve(clipService.getActiveClipsMetaRelative()).toString());
        resp.put("clips_meta_active", clipService.getActiveClipsMetaRelative());
        resp.put("clips_meta_catalog", listClipsMetaCatalog());
        return resp;
    }

    /** Activate a pre-generated clips_meta*.json under clip_preview/ (instant reload). */
    @PostMapping("/clips-meta")
    public ResponseEntity<?> setClipsMeta(@RequestBody Map<String, Object> body) {
        try {
            Object raw = body.get("relative_path");
            if (raw == null) raw = body.get("relativePath");
            if (raw == null) {
                return ResponseEntity.badRequest().body(Map.of("detail", "relative_path is required"));
            }
            String rel = raw.toString().trim();
            if (rel.isEmpty()) {
                return ResponseEntity.badRequest().body(Map.of("detail", "relative_path is empty"));
            }
            clipService.switchToRelative(rel);
            Map<String, Object> ok = new LinkedHashMap<>();
            ok.put("clips_meta_active", clipService.getActiveClipsMetaRelative());
            ok.put("dataset_key", clipService.getDatasetKey().orElse(""));
            return ResponseEntity.ok(ok);
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(Map.of("detail", e.getMessage()));
        } catch (IOException e) {
            return ResponseEntity.internalServerError().body(Map.of("detail", e.getMessage()));
        }
    }

    private List<Map<String, Object>> listClipsMetaCatalog() {
        Path root = props.projectRootPath().normalize();
        Path preview = root.resolve("clip_preview");
        if (!Files.isDirectory(preview)) {
            return List.of();
        }
        List<Path> files;
        try (Stream<Path> stream = Files.list(preview)) {
            files = stream
                    .filter(Files::isRegularFile)
                    .filter(p -> {
                        String n = p.getFileName().toString().toLowerCase(Locale.ROOT);
                        return n.startsWith("clips_meta") && n.endsWith(".json");
                    })
                    .sorted(Comparator.comparing(p -> p.getFileName().toString().toLowerCase(Locale.ROOT)))
                    .collect(Collectors.toList());
        } catch (IOException e) {
            return List.of();
        }

        List<Map<String, Object>> out = new ArrayList<>();
        for (Path p : files) {
            Map<String, Object> row = new LinkedHashMap<>();
            String rel = root.relativize(p.normalize()).toString().replace('\\', '/');
            row.put("relative_path", rel);
            row.put("filename", p.getFileName().toString());
            row.put("active", rel.equals(clipService.getActiveClipsMetaRelative()));
            try {
                JsonNode n = mapper.readTree(p.toFile());
                if (n.hasNonNull("dataset_key")) {
                    row.put("dataset_key", n.get("dataset_key").asText());
                }
                if (n.hasNonNull("source_infos")) {
                    row.put("source_infos", n.get("source_infos").asText());
                }
                if (n.has("total_clips")) {
                    row.put("total_clips", n.get("total_clips").asInt());
                }
            } catch (IOException ignored) {
                row.put("parse_error", true);
            }
            out.add(row);
        }
        return out;
    }

    private List<String> discoverFiles(List<String> relativeDirs, List<String> suffixes) {
        LinkedHashSet<String> paths = new LinkedHashSet<>();
        for (String relativeDir : relativeDirs) {
            paths.addAll(discoverFiles(relativeDir, suffixes));
        }
        return List.copyOf(paths);
    }

    private List<String> discoverFiles(String relativeDir, List<String> suffixes) {
        Path root = props.projectRootPath();
        Path base = root.resolve(relativeDir).normalize();
        if (!base.startsWith(root.normalize()) || !Files.isDirectory(base)) {
            return List.of();
        }

        try (var stream = Files.walk(base, 6)) {
            return stream
                    .filter(Files::isRegularFile)
                    .filter(path -> hasSuffix(path.getFileName().toString(), suffixes))
                    .sorted(Comparator.comparing(path -> root.relativize(path).toString()))
                    .map(path -> root.relativize(path).toString().replace('\\', '/'))
                    .toList();
        } catch (IOException e) {
            return List.of();
        }
    }

    private boolean hasSuffix(String name, List<String> suffixes) {
        String lower = name.toLowerCase(Locale.ROOT);
        return suffixes.stream().anyMatch(lower::endsWith);
    }
}
