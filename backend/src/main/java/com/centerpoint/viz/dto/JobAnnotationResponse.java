package com.centerpoint.viz.dto;

import java.util.ArrayList;
import java.util.List;

public class JobAnnotationResponse {
    private String jobId;
    private String note = "";
    private List<JobAnnotationMarker> markers = new ArrayList<>();
    private double createdAt;
    private double updatedAt;

    public String getJobId() { return jobId; }
    public void setJobId(String jobId) { this.jobId = jobId; }

    public String getNote() { return note; }
    public void setNote(String note) { this.note = note; }

    public List<JobAnnotationMarker> getMarkers() { return markers; }
    public void setMarkers(List<JobAnnotationMarker> markers) { this.markers = markers; }

    public double getCreatedAt() { return createdAt; }
    public void setCreatedAt(double createdAt) { this.createdAt = createdAt; }

    public double getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(double updatedAt) { this.updatedAt = updatedAt; }
}
