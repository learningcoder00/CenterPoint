package com.centerpoint.viz.controller;

import com.centerpoint.viz.dto.TagsRequest;
import com.centerpoint.viz.repository.ClipStarRepository;
import com.centerpoint.viz.repository.TagRepository;
import com.centerpoint.viz.service.ClipService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.io.IOException;
import java.util.*;

@RestController
@RequestMapping("/api/clips")
public class ClipController {

    private final ClipService clipService;
    private final TagRepository tagRepo;
    private final ClipStarRepository clipStarRepo;

    public ClipController(ClipService clipService, TagRepository tagRepo, ClipStarRepository clipStarRepo) {
        this.clipService = clipService;
        this.tagRepo = tagRepo;
        this.clipStarRepo = clipStarRepo;
    }

    @GetMapping
    public ResponseEntity<?> listClips() {
        try {
            List<JsonNode> clips = clipService.listClips();
            Map<String, List<String>> allTags = tagRepo.findAll();
            Set<String> starred = clipStarRepo.findAllStarredClipIds();
            List<ObjectNode> result = new ArrayList<>();
            for (JsonNode clip : clips) {
                ObjectNode c = clip.deepCopy();
                String clipId = c.get("clip_id").asText();
                c.putPOJO("tags", allTags.getOrDefault(clipId, Collections.emptyList()));
                c.put("starred", starred.contains(clipId));
                result.add(c);
            }
            Map<String, Object> resp = new LinkedHashMap<>();
            resp.put("clips", result);
            resp.put("total", result.size());
            resp.put("starred_count", starred.size());
            return ResponseEntity.ok(resp);
        } catch (IllegalStateException e) {
            return ResponseEntity.status(404).body(Map.of("detail", e.getMessage()));
        } catch (IOException e) {
            return ResponseEntity.status(500).body(Map.of("detail", e.getMessage()));
        }
    }

    @GetMapping("/{clipId}")
    public ResponseEntity<?> getClip(@PathVariable String clipId) {
        try {
            Optional<JsonNode> clipOpt = clipService.getClip(clipId);
            if (clipOpt.isEmpty()) {
                return ResponseEntity.status(404).body(Map.of("detail", "Clip not found"));
            }
            ObjectNode clip = clipOpt.get().deepCopy();
            List<String> tags = tagRepo.findByClipId(clipId);
            clip.putPOJO("tags", tags);
            clip.put("starred", clipStarRepo.findAllStarredClipIds().contains(clipId));
            return ResponseEntity.ok(clip);
        } catch (IOException e) {
            return ResponseEntity.status(500).body(Map.of("detail", e.getMessage()));
        }
    }

    @GetMapping("/{clipId}/tags")
    public ResponseEntity<?> getTags(@PathVariable String clipId) {
        List<String> tags = tagRepo.findByClipId(clipId);
        return ResponseEntity.ok(Map.of("tags", tags));
    }

    @PutMapping("/{clipId}/tags")
    public ResponseEntity<?> putTags(@PathVariable String clipId, @RequestBody TagsRequest body) {
        tagRepo.upsert(clipId, body.getTags());
        Map<String, Object> resp = new LinkedHashMap<>();
        resp.put("clip_id", clipId);
        resp.put("tags", body.getTags());
        return ResponseEntity.ok(resp);
    }

    /**
     * Star a clip so it shows up in the "Starred" filter on the Clips page.
     * Idempotent: starring an already-starred clip refreshes the timestamp.
     */
    @PostMapping("/{clipId}/star")
    public ResponseEntity<?> starClip(@PathVariable String clipId) {
        try {
            if (!clipService.exists(clipId)) {
                return ResponseEntity.status(404).body(Map.of("detail", "Clip not found"));
            }
            clipStarRepo.star(clipId);
            return ResponseEntity.ok(Map.of("clip_id", clipId, "starred", true));
        } catch (IOException e) {
            return ResponseEntity.status(500).body(Map.of("detail", e.getMessage()));
        }
    }

    @DeleteMapping("/{clipId}/star")
    public ResponseEntity<?> unstarClip(@PathVariable String clipId) {
        boolean removed = clipStarRepo.unstar(clipId);
        if (!removed) {
            return ResponseEntity.status(404).body(Map.of("detail", "Clip not starred"));
        }
        return ResponseEntity.ok(Map.of("clip_id", clipId, "starred", false));
    }
}
