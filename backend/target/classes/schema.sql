CREATE TABLE IF NOT EXISTS jobs (
    job_id     TEXT PRIMARY KEY,
    clip_id    TEXT NOT NULL,
    config     TEXT NOT NULL DEFAULT '',
    checkpoint TEXT NOT NULL DEFAULT '',
    status     TEXT NOT NULL DEFAULT 'pending',
    progress   INTEGER NOT NULL DEFAULT 0,
    total      INTEGER NOT NULL DEFAULT 0,
    mp4_path   TEXT,
    log        TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_clip ON jobs(clip_id);

CREATE TABLE IF NOT EXISTS tags (
    clip_id TEXT PRIMARY KEY,
    tags    TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS ai_optimizations (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id     TEXT NOT NULL,
    description TEXT NOT NULL,
    response    TEXT NOT NULL,
    created_at REAL NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);

CREATE INDEX IF NOT EXISTS idx_ai_optimizations_job ON ai_optimizations(job_id);
