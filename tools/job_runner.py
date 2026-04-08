"""
Async job runner for clip visualization tasks.

Each job:
  1. calls visualize_results.py (subprocess) with the clip's frame tokens
  2. sorts output jpg files by timestamp
  3. calls ffmpeg to stitch them into an MP4
  4. updates the job status in SQLite
"""

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Optional

import aiosqlite

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLIPS_META_PATH = PROJECT_ROOT / "clip_preview" / "clips_meta.json"
VIS_SCRIPT = PROJECT_ROOT / "tools" / "visualize_results.py"
JOBS_DIR = PROJECT_ROOT / "work_dirs" / "vis_jobs"
DB_PATH = PROJECT_ROOT / "work_dirs" / "clip_jobs.db"

_clips_meta_cache: Optional[dict] = None
_semaphore: Optional[asyncio.Semaphore] = None


def get_semaphore(concurrency: int = 1) -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(concurrency)
    return _semaphore


def load_clips_meta() -> dict:
    global _clips_meta_cache
    if _clips_meta_cache is None:
        with open(CLIPS_META_PATH, "r") as f:
            data = json.load(f)
        _clips_meta_cache = {c["clip_id"]: c for c in data.get("clips", [])}
    return _clips_meta_cache


async def init_db():
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute("""
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
            )
        """)
        for col, default in [("config", "''"), ("checkpoint", "''")]:
            try:
                await db.execute(f"ALTER TABLE jobs ADD COLUMN {col} TEXT NOT NULL DEFAULT {default}")
            except Exception:
                pass
        await db.execute("CREATE INDEX IF NOT EXISTS idx_jobs_clip ON jobs(clip_id)")
        await db.execute("CREATE TABLE IF NOT EXISTS tags (clip_id TEXT PRIMARY KEY, tags TEXT NOT NULL DEFAULT '[]')")
        await db.commit()


async def create_job(clip_id: str, config: str = "", checkpoint: str = "") -> dict:
    import time
    clips = load_clips_meta()
    if clip_id not in clips:
        raise ValueError(f"Unknown clip_id: {clip_id}")
    job_id = uuid.uuid4().hex
    now = time.time()
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute(
            "INSERT INTO jobs (job_id, clip_id, config, checkpoint, status, total, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
            (job_id, clip_id, config, checkpoint, "pending", clips[clip_id]["frame_count"], now, now),
        )
        await db.commit()
    return {"job_id": job_id, "clip_id": clip_id, "status": "pending"}


async def get_job(job_id: str) -> Optional[dict]:
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)) as cur:
            row = await cur.fetchone()
    if row is None:
        return None
    return dict(row)


async def list_jobs() -> list:
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM jobs ORDER BY created_at DESC") as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def delete_job(job_id: str) -> bool:
    import shutil
    job = await get_job(job_id)
    if not job:
        return False
    job_dir = JOBS_DIR / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir, ignore_errors=True)
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute("DELETE FROM jobs WHERE job_id=?", (job_id,))
        await db.commit()
    return True


async def _update_job(db, job_id: str, **kwargs):
    import time
    kwargs["updated_at"] = time.time()
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [job_id]
    await db.execute(f"UPDATE jobs SET {sets} WHERE job_id=?", vals)
    await db.commit()


async def run_job(job_id: str, config: str, checkpoint: str):
    """Execute a single clip visualization job (blocking within semaphore).

    Uses an atomic DB compare-and-swap (pending -> running) to ensure only
    ONE worker ever executes a given job, even if run_job is called multiple
    times (e.g. after server restarts or duplicate submissions).
    """
    import time

    # Atomic guard: only proceed if the job is still 'pending'
    now = time.time()
    async with aiosqlite.connect(str(DB_PATH)) as db:
        result = await db.execute(
            "UPDATE jobs SET status='running', updated_at=? WHERE job_id=? AND status='pending'",
            (now, job_id),
        )
        await db.commit()
        if result.rowcount == 0:
            # Job was already picked up by another worker (or not pending), skip
            return

    sem = get_semaphore()
    async with sem:
        await _execute_job(job_id, config, checkpoint)


async def _execute_job(job_id: str, config: str, checkpoint: str):
    import time

    clips = load_clips_meta()
    job = await get_job(job_id)
    if not job:
        return

    clip_id = job["clip_id"]
    clip = clips[clip_id]
    tokens = [f["token"] for f in clip["frames"]]
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = job_dir / "frames"
    frames_dir.mkdir(exist_ok=True)

    async with aiosqlite.connect(str(DB_PATH)) as db:
        await _update_job(db, job_id, log="Starting inference...\n")

    # --- Step 1: Run visualize_results.py ---
    cmd = [
        sys.executable,
        str(VIS_SCRIPT),
        "--config", config,
        "--checkpoint", checkpoint,
        "--tokens", *tokens,
        "--output-dir", str(frames_dir),
    ]

    log_lines = [f"[inference] cmd: {' '.join(cmd[:6])} ... ({len(tokens)} tokens)\n"]
    env = os.environ.copy()
    # Ensure det3d and other project modules are importable inside the subprocess
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(PROJECT_ROOT) + (os.pathsep + existing if existing else "")

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=str(PROJECT_ROOT),
        env=env,
    )

    completed_frames = 0
    async for line_bytes in proc.stdout:
        line = line_bytes.decode(errors="replace")
        log_lines.append(line)
        if line.startswith("  Saved:"):
            completed_frames += 1
            async with aiosqlite.connect(str(DB_PATH)) as db:
                await _update_job(
                    db, job_id,
                    progress=completed_frames,
                    log="".join(log_lines[-200:]),
                )

    await proc.wait()
    if proc.returncode != 0:
        async with aiosqlite.connect(str(DB_PATH)) as db:
            await _update_job(db, job_id, status="failed", log="".join(log_lines[-200:]))
        return

    # --- Step 2: Stitch frames into MP4 with ffmpeg ---
    jpg_files = sorted(frames_dir.glob("*.jpg"))
    if not jpg_files:
        async with aiosqlite.connect(str(DB_PATH)) as db:
            await _update_job(db, job_id, status="failed", log="No frames produced by visualize_results.py")
        return

    async with aiosqlite.connect(str(DB_PATH)) as db:
        await _update_job(db, job_id, status="stitching", log="".join(log_lines[-200:]))

    # Build a concat file list for ffmpeg (handles non-sequential naming)
    concat_list_path = job_dir / "concat.txt"
    with open(concat_list_path, "w") as f:
        for jpg in jpg_files:
            f.write(f"file '{jpg.resolve()}'\n")
            f.write("duration 0.5\n")  # 2 FPS = 0.5s per frame

    mp4_path = job_dir / f"{clip_id}.mp4"
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_list_path),
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(mp4_path),
    ]

    log_lines.append(f"\n[ffmpeg] stitching {len(jpg_files)} frames -> {mp4_path.name}\n")
    ffmpeg_proc = await asyncio.create_subprocess_exec(
        *ffmpeg_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=str(PROJECT_ROOT),
    )
    ffmpeg_out, _ = await ffmpeg_proc.communicate()
    log_lines.append(ffmpeg_out.decode(errors="replace"))

    if ffmpeg_proc.returncode != 0:
        async with aiosqlite.connect(str(DB_PATH)) as db:
            await _update_job(db, job_id, status="failed", log="".join(log_lines[-200:]))
        return

    async with aiosqlite.connect(str(DB_PATH)) as db:
        await _update_job(
            db, job_id,
            status="completed",
            mp4_path=str(mp4_path),
            progress=len(jpg_files),
            total=len(jpg_files),
            log="".join(log_lines[-200:]),
        )
