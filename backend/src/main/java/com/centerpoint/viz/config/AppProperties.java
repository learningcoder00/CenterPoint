package com.centerpoint.viz.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "app")
public class AppProperties {

    private String projectRoot;
    private String config = "";
    private String checkpoint = "";
    private String pythonExecutable = "python";
    private String visScript = "tools/visualize_results.py";
    private String jobsDir = "work_dirs/vis_jobs";
    private String clipsMeta = "clip_preview/clips_meta.json";
    private String vueDist = "frontend/dist";

    public String getProjectRoot() { return projectRoot; }
    public void setProjectRoot(String v) { this.projectRoot = v; }
    public String getConfig() { return config; }
    public void setConfig(String v) { this.config = v; }
    public String getCheckpoint() { return checkpoint; }
    public void setCheckpoint(String v) { this.checkpoint = v; }
    public String getPythonExecutable() { return pythonExecutable; }
    public void setPythonExecutable(String v) { this.pythonExecutable = v; }
    public String getVisScript() { return visScript; }
    public void setVisScript(String v) { this.visScript = v; }
    public String getJobsDir() { return jobsDir; }
    public void setJobsDir(String v) { this.jobsDir = v; }
    public String getClipsMeta() { return clipsMeta; }
    public void setClipsMeta(String v) { this.clipsMeta = v; }
    public String getVueDist() { return vueDist; }
    public void setVueDist(String v) { this.vueDist = v; }

    public java.nio.file.Path projectRootPath() {
        return java.nio.file.Paths.get(projectRoot);
    }
}
