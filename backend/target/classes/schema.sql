CREATE TABLE IF NOT EXISTS jobs (
    job_id       TEXT PRIMARY KEY,
    clip_id      TEXT NOT NULL,
    config       TEXT NOT NULL DEFAULT '',
    checkpoint   TEXT NOT NULL DEFAULT '',
    config_b     TEXT NOT NULL DEFAULT '',
    checkpoint_b TEXT NOT NULL DEFAULT '',
    visualization_mode TEXT NOT NULL DEFAULT 'bev_cameras',
    status       TEXT NOT NULL DEFAULT 'pending',
    progress     INTEGER NOT NULL DEFAULT 0,
    total        INTEGER NOT NULL DEFAULT 0,
    mp4_path     TEXT,
    log          TEXT NOT NULL DEFAULT '',
    created_at   REAL NOT NULL,
    updated_at   REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_clip ON jobs(clip_id);

CREATE TABLE IF NOT EXISTS tags (
    clip_id TEXT PRIMARY KEY,
    tags    TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS ai_optimizations (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id     TEXT NOT NULL,
    clip_id    TEXT,
    description TEXT NOT NULL,
    response    TEXT NOT NULL,
    created_at REAL NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);

CREATE INDEX IF NOT EXISTS idx_ai_optimizations_job ON ai_optimizations(job_id);
CREATE INDEX IF NOT EXISTS idx_ai_optimizations_clip ON ai_optimizations(clip_id);

CREATE TABLE IF NOT EXISTS job_video_annotations (
    job_id       TEXT PRIMARY KEY,
    note         TEXT NOT NULL DEFAULT '',
    markers_json TEXT NOT NULL DEFAULT '[]',
    created_at   REAL NOT NULL,
    updated_at   REAL NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);

CREATE INDEX IF NOT EXISTS idx_job_video_annotations_updated_at ON job_video_annotations(updated_at);

CREATE TABLE IF NOT EXISTS job_reviews (
    job_id         TEXT PRIMARY KEY,
    review_status  TEXT NOT NULL DEFAULT 'unreviewed',
    reviewer_note  TEXT NOT NULL DEFAULT '',
    updated_at     REAL NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);

CREATE INDEX IF NOT EXISTS idx_job_reviews_status ON job_reviews(review_status);

CREATE TABLE IF NOT EXISTS clip_stars (
    clip_id    TEXT PRIMARY KEY,
    starred_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS job_stars (
    job_id     TEXT PRIMARY KEY,
    starred_at REAL NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);
