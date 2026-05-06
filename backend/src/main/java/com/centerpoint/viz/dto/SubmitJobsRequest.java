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
    /** Side-B config, only used when visualization_mode == "bev_compare". */
    @JsonProperty("config_b")
    private String configB;
    /** Side-B checkpoint, only used when visualization_mode == "bev_compare". */
    @JsonProperty("checkpoint_b")
    private String checkpointB;

    /**
     * If true (default), reuse the latest completed job whose parameters fully
     * match instead of running inference again. Set false to force a new job.
     */
    @JsonProperty("reuse_completed")
    private Boolean reuseCompleted;

    public List<String> getClipIds() { return clipIds; }
    public void setClipIds(List<String> v) { this.clipIds = v; }
    public String getConfig() { return config; }
    public void setConfig(String v) { this.config = v; }
    public String getCheckpoint() { return checkpoint; }
    public void setCheckpoint(String v) { this.checkpoint = v; }
    public String getVisualizationMode() { return visualizationMode; }
    public void setVisualizationMode(String v) { this.visualizationMode = v; }
    public String getConfigB() { return configB; }
    public void setConfigB(String v) { this.configB = v; }
    public String getCheckpointB() { return checkpointB; }
    public void setCheckpointB(String v) { this.checkpointB = v; }
    public Boolean getReuseCompleted() { return reuseCompleted; }
    public void setReuseCompleted(Boolean v) { this.reuseCompleted = v; }
}
