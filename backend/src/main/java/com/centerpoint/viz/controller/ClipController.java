package com.centerpoint.viz.controller;

import com.centerpoint.viz.dto.TagsRequest;
import com.centerpoint.viz.repository.TagRepository;
import com.centerpoint.viz.service.ClipService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
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
    private final ObjectMapper mapper = new ObjectMapper();

    public ClipController(ClipService clipService, TagRepository tagRepo) {
        this.clipService = clipService;
        this.tagRepo = tagRepo;
    }

    @GetMapping
    public ResponseEntity<?> listClips() {
        try {
            List<JsonNode> clips = clipService.listClips();
            Map<String, List<String>> allTags = tagRepo.findAll();
            List<ObjectNode> result = new ArrayList<>();
            for (JsonNode clip : clips) {
                ObjectNode c = clip.deepCopy();
                String clipId = c.get("clip_id").asText();
                c.putPOJO("tags", allTags.getOrDefault(clipId, Collections.emptyList()));
                result.add(c);
            }
            Map<String, Object> resp = new LinkedHashMap<>();
            resp.put("clips", result);
            resp.put("total", result.size());
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
}
