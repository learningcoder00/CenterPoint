package com.centerpoint.viz.controller;

import com.centerpoint.viz.config.AppProperties;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/config")
public class ConfigController {

    private final AppProperties props;

    public ConfigController(AppProperties props) {
        this.props = props;
    }

    @GetMapping
    public Map<String, Object> getConfig() {
        Map<String, Object> resp = new LinkedHashMap<>();
        resp.put("config", props.getConfig());
        resp.put("checkpoint", props.getCheckpoint());
        resp.put("configs", discoverFiles("configs", List.of(".py")));
        resp.put("checkpoints", discoverFiles(List.of("work_dirs", "checkpoints", "weights"), List.of(".pth", ".pt", ".ckpt")));
        resp.put("clips_meta", props.projectRootPath().resolve(props.getClipsMeta()).toString());
        return resp;
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
        String lower = name.toLowerCase();
        return suffixes.stream().anyMatch(lower::endsWith);
    }
}
