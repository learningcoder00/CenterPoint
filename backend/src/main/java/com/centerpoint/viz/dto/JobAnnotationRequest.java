package com.centerpoint.viz.dto;

import java.util.ArrayList;
import java.util.List;

public class JobAnnotationRequest {
    private String note = "";
    private List<JobAnnotationMarker> markers = new ArrayList<>();

    public String getNote() { return note; }
    public void setNote(String note) { this.note = note; }

    public List<JobAnnotationMarker> getMarkers() { return markers; }
    public void setMarkers(List<JobAnnotationMarker> markers) { this.markers = markers; }
}
