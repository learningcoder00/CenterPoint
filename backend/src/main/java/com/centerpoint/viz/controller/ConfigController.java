package com.centerpoint.viz.controller;

import com.centerpoint.viz.config.AppProperties;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
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
        resp.put("clips_meta", props.projectRootPath().resolve(props.getClipsMeta()).toString());
        return resp;
    }
}
