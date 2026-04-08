#!/usr/bin/env python3
"""
FastAPI server for Clip Visualization System.

Usage:
    python tools/server.py \
        --config configs/nusc/voxelnet/nusc_centerpoint_voxelnet_0075voxel_fix_bn_z.py \
        --checkpoint work_dirs/epoch_20.pth \
        --port 8081
"""

import argparse
import asyncio
import json
import mimetypes
import os
import time
from pathlib import Path
from typing import List, Optional

import aiosqlite
import uvicorn
from contextlib import asynccontextmanager
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLIPS_META_PATH = PROJECT_ROOT / "clip_preview" / "clips_meta.json"
FRONTEND_DIR = PROJECT_ROOT / "tools" / "frontend"
DATA_DIR = PROJECT_ROOT  # static files root (serves clip_preview images etc.)

# ── populated at startup from CLI args ──────────────────────────────────────
_DEFAULT_CONFIG: str = ""
_DEFAULT_CHECKPOINT: str = ""

# ── lazy import to avoid circular deps ──────────────────────────────────────
import sys
sys.path.insert(0, str(PROJECT_ROOT / "tools"))
import job_runner as runner

@asynccontextmanager
async def lifespan(app: FastAPI):
    await runner.init_db()
    yield


app = FastAPI(title="CenterPoint Clip Viz", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic schemas ─────────────────────────────────────────────────────────
class SubmitJobsRequest(BaseModel):
    clip_ids: List[str]
    config: Optional[str] = None
    checkpoint: Optional[str] = None


class TagsRequest(BaseModel):
    tags: List[str]


# ─────────────────────────────────────────────────────────────────────────────
# Clip routes
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/clips")
async def list_clips():
    if not CLIPS_META_PATH.exists():
        raise HTTPException(404, "clips_meta.json not found. Run generate_clip_preview.py first.")
    with open(CLIPS_META_PATH) as f:
        data = json.load(f)
    clips = data.get("clips", [])
    # attach tags from DB
    async with aiosqlite.connect(str(runner.DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT clip_id, tags FROM tags") as cur:
            tag_rows = {r["clip_id"]: json.loads(r["tags"]) async for r in cur}
    for c in clips:
        c["tags"] = tag_rows.get(c["clip_id"], [])
        c.pop("frames", None)  # omit large frames array in list response
    return {"clips": clips, "total": len(clips)}


@app.get("/api/clips/{clip_id}")
async def get_clip(clip_id: str):
    clips = runner.load_clips_meta()
    if clip_id not in clips:
        raise HTTPException(404, "Clip not found")
    clip = dict(clips[clip_id])
    async with aiosqlite.connect(str(runner.DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT tags FROM tags WHERE clip_id=?", (clip_id,)) as cur:
            row = await cur.fetchone()
    clip["tags"] = json.loads(row["tags"]) if row else []
    return clip


@app.get("/api/clips/{clip_id}/tags")
async def get_tags(clip_id: str):
    async with aiosqlite.connect(str(runner.DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT tags FROM tags WHERE clip_id=?", (clip_id,)) as cur:
            row = await cur.fetchone()
    tags = json.loads(row["tags"]) if row else []
    return {"tags": tags}


@app.put("/api/clips/{clip_id}/tags")
async def put_tags(clip_id: str, body: TagsRequest):
    async with aiosqlite.connect(str(runner.DB_PATH)) as db:
        await db.execute(
            "INSERT INTO tags(clip_id, tags) VALUES(?,?) ON CONFLICT(clip_id) DO UPDATE SET tags=excluded.tags",
            (clip_id, json.dumps(body.tags)),
        )
        await db.commit()
    return {"clip_id": clip_id, "tags": body.tags}


# ─────────────────────────────────────────────────────────────────────────────
# Job routes
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/api/jobs", status_code=202)
async def submit_jobs(body: SubmitJobsRequest, background_tasks: BackgroundTasks):
    config = body.config or _DEFAULT_CONFIG
    checkpoint = body.checkpoint or _DEFAULT_CHECKPOINT

    if not config:
        raise HTTPException(400, "No config specified. Pass 'config' in body or start server with --config.")
    if not checkpoint:
        raise HTTPException(400, "No checkpoint specified. Pass 'checkpoint' in body or start server with --checkpoint.")

    created = []
    for clip_id in body.clip_ids:
        try:
            job = await runner.create_job(clip_id)
        except ValueError as e:
            raise HTTPException(400, str(e))
        background_tasks.add_task(runner.run_job, job["job_id"], config, checkpoint)
        created.append(job)
    return {"jobs": created}


@app.get("/api/jobs")
async def list_jobs():
    jobs = await runner.list_jobs()
    clips = runner.load_clips_meta()
    for j in jobs:
        c = clips.get(j["clip_id"], {})
        j["thumbnail_path"] = c.get("thumbnail_path", "")
        j["frame_count"] = c.get("frame_count", 0)
    return {"jobs": jobs}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    job = await runner.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str):
    ok = await runner.delete_job(job_id)
    if not ok:
        raise HTTPException(404, "Job not found")
    return {"deleted": job_id}


@app.get("/api/jobs/{job_id}/video")
async def stream_video(job_id: str):
    job = await runner.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job["status"] != "completed" or not job.get("mp4_path"):
        raise HTTPException(409, f"Video not ready. Job status: {job['status']}")
    mp4_path = Path(job["mp4_path"])
    if not mp4_path.exists():
        raise HTTPException(404, "MP4 file missing on disk")
    return FileResponse(
        str(mp4_path),
        media_type="video/mp4",
        filename=mp4_path.name,
        headers={"Accept-Ranges": "bytes"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Config info route (for frontend to know server defaults)
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/config")
async def server_config():
    return {
        "config": _DEFAULT_CONFIG,
        "checkpoint": _DEFAULT_CHECKPOINT,
        "clips_meta": str(CLIPS_META_PATH),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Static files: data images (for clip thumbnails) + frontend pages
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/")
async def index_redirect():
    return RedirectResponse(url="/clips.html")

# Serve project root so clip thumbnail paths (../data/nuscenes/...) resolve
# follow_symlink=True is required because data/nuscenes/v1.0.0 is a symlink to the dataset mount
app.mount("/data", StaticFiles(directory=str(PROJECT_ROOT / "data"), follow_symlink=True), name="data")
app.mount("/clip_preview", StaticFiles(directory=str(PROJECT_ROOT / "clip_preview")), name="clip_preview")
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────
def parse_args():
    parser = argparse.ArgumentParser(description="CenterPoint Clip Visualization Server")
    parser.add_argument("--config", default="", help="Default model config path")
    parser.add_argument("--checkpoint", default="", help="Default checkpoint path")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=8081, help="Bind port")
    parser.add_argument("--reload", action="store_true", help="Enable hot-reload (dev mode)")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    # Must assign globals BEFORE uvicorn starts; passing `app` object (not string)
    # avoids uvicorn re-importing this module and wiping the globals.
    _DEFAULT_CONFIG = args.config
    _DEFAULT_CHECKPOINT = args.checkpoint
    print(f"Starting server on http://0.0.0.0:{args.port}")
    print(f"  Config:     {args.config or '(not set)'}")
    print(f"  Checkpoint: {args.checkpoint or '(not set)'}")
    print(f"  Clips page: http://127.0.0.1:{args.port}/clips.html")
    print(f"  Results:    http://127.0.0.1:{args.port}/results.html")
    uvicorn.run(
        app,           # pass app object directly so this module is not re-imported
        host=args.host,
        port=args.port,
    )
