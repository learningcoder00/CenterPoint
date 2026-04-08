#!/usr/bin/env python3
import argparse
import json
import math
import os
import pickle
import shutil
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INFOS = PROJECT_ROOT / "data/nuScenes/infos_val_10sweeps_withvelo_filter_True.pkl"
TEMPLATE_HTML = PROJECT_ROOT / "tools/clip_viewer.html"


def parse_args():
    parser = argparse.ArgumentParser(description="Generate nuScenes clip preview page")
    parser.add_argument(
        "--infos",
        default=str(DEFAULT_INFOS),
        help="Path to infos_val_*.pkl",
    )
    parser.add_argument(
        "--output-dir",
        default="clip_preview",
        help="Directory for generated metadata and HTML",
    )
    parser.add_argument(
        "--target-clips",
        type=int,
        default=150,
        help="Target number of clips to generate",
    )
    parser.add_argument(
        "--gap-threshold",
        type=float,
        default=2.0,
        help="Timestamp gap threshold in seconds for initial clip splitting",
    )
    parser.add_argument(
        "--preferred-min-frames",
        type=int,
        default=50,
        help="Prefer splitting clips with at least this many frames",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host for --serve",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port for --serve",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Serve the generated page after writing files",
    )
    return parser.parse_args()


def load_infos(infos_path):
    with open(infos_path, "rb") as f:
        infos = pickle.load(f)
    return sorted(infos, key=lambda x: x["timestamp"])


def split_by_gap(infos, gap_threshold):
    clips = []
    current = [infos[0]]

    for prev, cur in zip(infos[:-1], infos[1:]):
        if cur["timestamp"] - prev["timestamp"] > gap_threshold:
            clips.append(current)
            current = [cur]
        else:
            current.append(cur)

    clips.append(current)
    return clips


def choose_split_index(clips, preferred_min_frames):
    preferred = [
        (idx, len(clip)) for idx, clip in enumerate(clips) if len(clip) >= preferred_min_frames
    ]
    if preferred:
        return max(preferred, key=lambda x: x[1])[0]

    fallback = [(idx, len(clip)) for idx, clip in enumerate(clips) if len(clip) >= 2]
    if not fallback:
        return None
    return max(fallback, key=lambda x: x[1])[0]


def refine_clips(clips, target_clips, preferred_min_frames):
    clips = [clip for clip in clips if clip]

    while len(clips) < target_clips:
        split_idx = choose_split_index(clips, preferred_min_frames)
        if split_idx is None:
            break

        clip = clips.pop(split_idx)
        mid = int(math.ceil(len(clip) / 2.0))
        left = clip[:mid]
        right = clip[mid:]

        if not left or not right:
            clips.insert(split_idx, clip)
            break

        clips.insert(split_idx, right)
        clips.insert(split_idx, left)

    return clips[:target_clips]


def build_clip_payload(clips, output_dir):
    output_dir = Path(output_dir).resolve()
    payload_clips = []

    for idx, clip in enumerate(clips):
        frames = []
        for info in clip:
            image_abs = PROJECT_ROOT / info["cam_front_path"]
            image_rel = Path(info["cam_front_path"])
            html_rel = Path(os.path.relpath(str(image_abs), str(output_dir)))
            frames.append(
                {
                    "token": info["token"],
                    "timestamp": float(info["timestamp"]),
                    "image_path": str(html_rel).replace("\\", "/"),
                    "project_path": str(image_rel).replace("\\", "/"),
                }
            )

        start_ts = float(clip[0]["timestamp"])
        end_ts = float(clip[-1]["timestamp"])
        payload_clips.append(
            {
                "clip_id": f"clip_{idx + 1:03d}",
                "clip_index": idx + 1,
                "frame_count": len(clip),
                "duration_s": round(end_ts - start_ts, 3),
                "start_timestamp": start_ts,
                "end_timestamp": end_ts,
                "start_token": clip[0]["token"],
                "end_token": clip[-1]["token"],
                "thumbnail_path": frames[0]["image_path"],
                "frames": frames,
            }
        )

    return payload_clips


def ensure_output_assets(output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(TEMPLATE_HTML, output_dir / "index.html")


def write_outputs(output_dir, metadata):
    ensure_output_assets(output_dir)
    with open(output_dir / "clips_meta.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)


def build_metadata(infos, clips, output_dir, args):
    payload_clips = build_clip_payload(clips, output_dir)
    return {
        "source_infos": str(Path(args.infos).resolve()),
        "project_root": str(PROJECT_ROOT),
        "target_clips": args.target_clips,
        "gap_threshold": args.gap_threshold,
        "preferred_min_frames": args.preferred_min_frames,
        "total_frames": len(infos),
        "total_clips": len(payload_clips),
        "fps": 2,
        "clips": payload_clips,
    }


def print_summary(initial_clips, final_clips):
    initial_sizes = [len(clip) for clip in initial_clips]
    final_sizes = [len(clip) for clip in final_clips]
    print(f"Initial clips: {len(initial_clips)}")
    print(
        "Initial clip sizes: "
        f"min={min(initial_sizes)}, max={max(initial_sizes)}, mean={sum(initial_sizes) / len(initial_sizes):.1f}"
    )
    print(f"Final clips: {len(final_clips)}")
    print(
        "Final clip sizes: "
        f"min={min(final_sizes)}, max={max(final_sizes)}, mean={sum(final_sizes) / len(final_sizes):.1f}"
    )


def serve_output(output_dir, host, port):
    handler = partial(SimpleHTTPRequestHandler, directory=str(PROJECT_ROOT))
    server = ThreadingHTTPServer((host, port), handler)
    index_rel = output_dir.resolve().relative_to(PROJECT_ROOT.resolve())
    index_path = f"/{str(index_rel).replace(chr(92), '/')}/index.html"
    bind_url = f"http://{host}:{port}{index_path}"
    local_url = f"http://127.0.0.1:{port}{index_path}"
    print(f"Serving project root: {PROJECT_ROOT}")
    print(f"Bind: {bind_url}")
    print(f"Open: {local_url}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()


def main():
    args = parse_args()
    output_dir = (PROJECT_ROOT / args.output_dir).resolve()

    print(f"Loading infos from {args.infos} ...")
    infos = load_infos(args.infos)
    print(f"Loaded {len(infos)} frames")

    initial_clips = split_by_gap(infos, args.gap_threshold)
    final_clips = refine_clips(initial_clips, args.target_clips, args.preferred_min_frames)
    print_summary(initial_clips, final_clips)

    metadata = build_metadata(infos, final_clips, output_dir, args)
    write_outputs(output_dir, metadata)

    print(f"Wrote: {output_dir / 'clips_meta.json'}")
    print(f"Wrote: {output_dir / 'index.html'}")

    if args.serve:
        serve_output(output_dir, args.host, args.port)


if __name__ == "__main__":
    main()
