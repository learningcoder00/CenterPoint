package com.centerpoint.viz.dto;

public class JobAnnotationMarker {
    private String id;
    private double timeSec;
    private String type = "bug";

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }

    public double getTimeSec() { return timeSec; }
    public void setTimeSec(double timeSec) { this.timeSec = timeSec; }

    public String getType() { return type; }
    public void setType(String type) { this.type = type; }
}
