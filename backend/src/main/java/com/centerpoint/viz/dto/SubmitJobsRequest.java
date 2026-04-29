package com.centerpoint.viz.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

public class SubmitJobsRequest {
    @JsonProperty("clip_ids")
    private List<String> clipIds;
    private String config;
    private String checkpoint;
    @JsonProperty("visualization_mode")
    private String visualizationMode;

    public List<String> getClipIds() { return clipIds; }
    public void setClipIds(List<String> v) { this.clipIds = v; }
    public String getConfig() { return config; }
    public void setConfig(String v) { this.config = v; }
    public String getCheckpoint() { return checkpoint; }
    public void setCheckpoint(String v) { this.checkpoint = v; }
    public String getVisualizationMode() { return visualizationMode; }
    public void setVisualizationMode(String v) { this.visualizationMode = v; }
}
