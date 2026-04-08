package com.centerpoint.viz.model;

public class Job {
    private String jobId;
    private String clipId;
    private String config;
    private String checkpoint;
    private String status;
    private int progress;
    private int total;
    private String mp4Path;
    private String log;
    private double createdAt;
    private double updatedAt;

    // enriched fields (not in DB, added in list response)
    private String thumbnailPath;
    private int frameCount;

    public String getJobId() { return jobId; }
    public void setJobId(String v) { this.jobId = v; }
    public String getClipId() { return clipId; }
    public void setClipId(String v) { this.clipId = v; }
    public String getConfig() { return config; }
    public void setConfig(String v) { this.config = v; }
    public String getCheckpoint() { return checkpoint; }
    public void setCheckpoint(String v) { this.checkpoint = v; }
    public String getStatus() { return status; }
    public void setStatus(String v) { this.status = v; }
    public int getProgress() { return progress; }
    public void setProgress(int v) { this.progress = v; }
    public int getTotal() { return total; }
    public void setTotal(int v) { this.total = v; }
    public String getMp4Path() { return mp4Path; }
    public void setMp4Path(String v) { this.mp4Path = v; }
    public String getLog() { return log; }
    public void setLog(String v) { this.log = v; }
    public double getCreatedAt() { return createdAt; }
    public void setCreatedAt(double v) { this.createdAt = v; }
    public double getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(double v) { this.updatedAt = v; }
    public String getThumbnailPath() { return thumbnailPath; }
    public void setThumbnailPath(String v) { this.thumbnailPath = v; }
    public int getFrameCount() { return frameCount; }
    public void setFrameCount(int v) { this.frameCount = v; }
}
