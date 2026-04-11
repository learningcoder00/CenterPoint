package com.centerpoint.viz.controller;

import com.centerpoint.viz.config.AppProperties;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.core.io.FileSystemResource;
import org.springframework.core.io.Resource;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ResponseBody;

import java.nio.file.Path;

/**
 * Catches all non-API, non-static requests and returns the Vue SPA index.html.
 * This enables client-side routing (/clips, /results, etc.) to work on page refresh.
 */
@Controller
public class SpaController {

    private final AppProperties props;

    public SpaController(AppProperties props) {
        this.props = props;
    }

    @GetMapping(value = {"/", "/clips", "/results", "/ai-optimization"})
    @ResponseBody
    public ResponseEntity<Resource> spa(HttpServletRequest request) {
        Path indexHtml = props.projectRootPath()
            .resolve(props.getVueDist())
            .resolve("index.html");
        Resource res = new FileSystemResource(indexHtml);
        if (!res.exists()) {
            return ResponseEntity.status(404).build();
        }
        return ResponseEntity.ok()
            .header("Content-Type", "text/html; charset=UTF-8")
            .body(res);
    }
}
