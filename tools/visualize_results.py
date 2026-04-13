"""
Visualize CenterPoint detection results:
  - Center: BEV with detection boxes (no point cloud)
  - Left:   3 forward-facing camera images with projected 3D boxes
  - Right:  3 backward-facing camera images with projected 3D boxes

Usage (config + checkpoint, runs inference internally):
    python tools/visualize_results.py \
        --config configs/nusc/voxelnet/nusc_centerpoint_voxelnet_0075voxel_fix_bn_z.py \
        --checkpoint work_dirs/nusc_centerpoint_voxelnet_0075voxel_fix_bn_z/latest.pth \
        --output-dir vis_output \
        --score-threshold 0.3 \
        --max-samples 10

Usage (pre-computed prediction pkl, skip inference):
    python tools/visualize_results.py \
        --prediction work_dirs/prediction.pkl \
        --infos data/nuScenes/infos_val_10sweeps_withvelo_filter_True.pkl \
        --data-root data/nuScenes \
        --output-dir vis_output \
        --score-threshold 0.3 \
        --max-samples 10
"""

import argparse
import datetime
import os
import pickle
from copy import deepcopy

import cv2
import numpy as np
import torch
from pyquaternion import Quaternion

from det3d.torchie import Config
from det3d.models import build_detector
from det3d.datasets import build_dataloader, build_dataset
from det3d.torchie.apis import batch_processor
from det3d.torchie.trainer import load_checkpoint

CAM_CHANS = [
    "CAM_FRONT", "CAM_FRONT_RIGHT", "CAM_BACK_RIGHT",
    "CAM_BACK", "CAM_BACK_LEFT", "CAM_FRONT_LEFT",
]

FRONT_CAM_INDICES = [5, 0, 1]  # CAM_FRONT_LEFT, CAM_FRONT, CAM_FRONT_RIGHT
BACK_CAM_INDICES = [4, 3, 2]   # CAM_BACK_LEFT, CAM_BACK, CAM_BACK_RIGHT

FRONT_CAM_NAMES = ["CAM_FRONT_LEFT", "CAM_FRONT", "CAM_FRONT_RIGHT"]
BACK_CAM_NAMES = ["CAM_BACK_LEFT", "CAM_BACK", "CAM_BACK_RIGHT"]

CLASS_NAMES = [
    "car", "truck", "construction_vehicle", "bus", "trailer",
    "barrier", "motorcycle", "bicycle", "pedestrian", "traffic_cone",
]

CLASS_COLORS_BGR = [
    (255, 120, 0),    # car - blue
    (0, 160, 255),    # truck - orange
    (0, 220, 255),    # construction_vehicle - yellow
    (0, 200, 0),      # bus - green
    (200, 200, 0),    # trailer - cyan
    (200, 0, 200),    # barrier - purple
    (0, 0, 255),      # motorcycle - red
    (150, 100, 255),  # bicycle - pink
    (0, 255, 0),      # pedestrian - lime
    (255, 0, 255),    # traffic_cone - magenta
]

BEV_RESOLUTION = 1350
CAM_DISPLAY_W = 800
CAM_DISPLAY_H = 450


def corners_3d_box(center, wlh, orientation):
    """Compute 8 corners of a 3D box, returns (3, 8)."""
    w, l, h = wlh
    x_corners = l / 2 * np.array([1,  1,  1,  1, -1, -1, -1, -1])
    y_corners = w / 2 * np.array([1, -1, -1,  1,  1, -1, -1,  1])
    z_corners = h / 2 * np.array([1,  1, -1, -1,  1,  1, -1, -1])
    corners = np.vstack((x_corners, y_corners, z_corners))
    corners = orientation.rotation_matrix @ corners
    corners[0, :] += center[0]
    corners[1, :] += center[1]
    corners[2, :] += center[2]
    return corners


def parse_detections(detection, score_threshold=0.3):
    """Parse detection dict into list of (center, wlh, quat, label, score)."""
    box3d = detection["box3d_lidar"]
    scores = detection["scores"]
    labels = detection["label_preds"]

    if hasattr(box3d, "numpy"):
        box3d = box3d.detach().cpu().numpy()
    if hasattr(scores, "numpy"):
        scores = scores.detach().cpu().numpy()
    if hasattr(labels, "numpy"):
        labels = labels.detach().cpu().numpy()

    box3d = box3d.copy()
    box3d[:, -1] = -box3d[:, -1] - np.pi / 2

    results = []
    for i in range(box3d.shape[0]):
        if scores[i] < score_threshold:
            continue
        center = box3d[i, :3]
        wlh = box3d[i, 3:6]
        yaw = box3d[i, -1]
        quat = Quaternion(axis=[0, 0, 1], radians=yaw)
        results.append((center, wlh, quat, int(labels[i]), float(scores[i])))
    return results


def draw_bev(detections, bev_range=54.0):
    """Draw BEV image with detection boxes only."""
    img = np.zeros((BEV_RESOLUTION, BEV_RESOLUTION, 3), dtype=np.uint8)
    img[:] = (40, 40, 40)

    scale = BEV_RESOLUTION / (2 * bev_range)

    cv2.line(img, (BEV_RESOLUTION // 2, 0), (BEV_RESOLUTION // 2, BEV_RESOLUTION),
             (60, 60, 60), 1)
    cv2.line(img, (0, BEV_RESOLUTION // 2), (BEV_RESOLUTION, BEV_RESOLUTION // 2),
             (60, 60, 60), 1)

    for r in [10, 20, 30, 40, 50]:
        radius_px = int(r * scale)
        cv2.circle(img, (BEV_RESOLUTION // 2, BEV_RESOLUTION // 2), radius_px,
                   (60, 60, 60), 1)

    for center, wlh, quat, label, score in detections:
        corners = corners_3d_box(center, wlh, quat)
        bottom_corners = corners[:2, [2, 3, 7, 6]]  # bottom face corners in xy

        pts = np.zeros((4, 2), dtype=np.int32)
        for j in range(4):
            px = int(bottom_corners[0, j] * scale + BEV_RESOLUTION / 2)
            py = int(-bottom_corners[1, j] * scale + BEV_RESOLUTION / 2)
            pts[j] = [px, py]

        color = CLASS_COLORS_BGR[label % len(CLASS_COLORS_BGR)]
        cv2.polylines(img, [pts], isClosed=True, color=color, thickness=2)

        front_mid = ((pts[0] + pts[1]) // 2).astype(int)
        center_mid = np.mean(pts, axis=0).astype(int)
        cv2.line(img, tuple(front_mid), tuple(center_mid), color, 2)

    ego_size = 8
    cx, cy = BEV_RESOLUTION // 2, BEV_RESOLUTION // 2
    ego_pts = np.array([
        [cx, cy - ego_size * 2],
        [cx - ego_size, cy + ego_size],
        [cx + ego_size, cy + ego_size],
    ], dtype=np.int32)
    cv2.fillPoly(img, [ego_pts], (255, 255, 255))

    return img


def project_box_to_image(corners_3d, extrinsic, intrinsic, img_w, img_h):
    """
    Project 3D box corners to image.
    corners_3d: (3, 8) in lidar frame
    extrinsic: (4, 4) lidar-to-camera
    intrinsic: (3, 3) camera intrinsic
    Returns: (8, 2) pixel coordinates or None if box is behind camera.
    """
    corners_homo = np.vstack([corners_3d, np.ones((1, 8))])  # (4, 8)
    corners_cam = extrinsic @ corners_homo  # (4, 8)
    corners_cam = corners_cam[:3, :]  # (3, 8)

    depths = corners_cam[2, :]
    if np.all(depths <= 0):
        return None

    corners_img = intrinsic @ corners_cam  # (3, 8)

    valid = depths > 0.1
    corners_img[:, valid] = corners_img[:, valid] / corners_img[2:3, valid]

    corners_2d = corners_img[:2, :].T  # (8, 2)

    in_image = (
        valid &
        (corners_2d[:, 0] >= -img_w) & (corners_2d[:, 0] < 2 * img_w) &
        (corners_2d[:, 1] >= -img_h) & (corners_2d[:, 1] < 2 * img_h)
    )

    if np.sum(in_image) < 2:
        return None

    corners_2d[~valid] = np.nan
    return corners_2d


def draw_3d_box_on_image(img, corners_2d, color, linewidth=2):
    """
    Draw 3D box edges on image from projected 2D corners.
    corners_2d: (8, 2), same order as Box.corners().
    """
    edges_front = [(0, 1), (1, 2), (2, 3), (3, 0)]
    edges_back = [(4, 5), (5, 6), (6, 7), (7, 4)]
    edges_connect = [(0, 4), (1, 5), (2, 6), (3, 7)]

    def _draw_line(p1, p2, c, lw):
        if np.any(np.isnan(p1)) or np.any(np.isnan(p2)):
            return
        cv2.line(img,
                 (int(round(p1[0])), int(round(p1[1]))),
                 (int(round(p2[0])), int(round(p2[1]))),
                 c, lw, cv2.LINE_AA)

    for i, j in edges_front:
        _draw_line(corners_2d[i], corners_2d[j], color, linewidth)
    for i, j in edges_back:
        _draw_line(corners_2d[i], corners_2d[j],
                   tuple(int(c * 0.6) for c in color), linewidth)
    for i, j in edges_connect:
        _draw_line(corners_2d[i], corners_2d[j],
                   tuple(int(c * 0.8) for c in color), linewidth)


def draw_camera_image(img_path, detections, extrinsic, intrinsic, cam_name):
    """Load camera image and draw projected 3D boxes."""
    img = cv2.imread(img_path)
    if img is None:
        img = np.zeros((900, 1600, 3), dtype=np.uint8)
        cv2.putText(img, f"Image not found: {cam_name}", (50, 450),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
        return cv2.resize(img, (CAM_DISPLAY_W, CAM_DISPLAY_H))

    h, w = img.shape[:2]
    extrinsic = np.array(extrinsic)
    intrinsic = np.array(intrinsic)

    for center, wlh, quat, label, score in detections:
        corners = corners_3d_box(center, wlh, quat)
        corners_2d = project_box_to_image(corners, extrinsic, intrinsic, w, h)
        if corners_2d is not None:
            color = CLASS_COLORS_BGR[label % len(CLASS_COLORS_BGR)]
            draw_3d_box_on_image(img, corners_2d, color, linewidth=2)

    cv2.putText(img, cam_name, (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2, cv2.LINE_AA)

    return cv2.resize(img, (CAM_DISPLAY_W, CAM_DISPLAY_H))


def compose_visualization(bev_img, front_imgs, back_imgs):
    """
    Compose final image:
      [front_left ]                 [back_left  ]
      [front      ]  [   BEV   ]   [back       ]
      [front_right]                 [back_right ]
    """
    left_col = np.vstack(front_imgs)
    right_col = np.vstack(back_imgs)
    cam_h = left_col.shape[0]

    bev_resized = cv2.resize(bev_img, (cam_h, cam_h))

    canvas = np.hstack([left_col, bev_resized, right_col])
    return canvas


def add_legend(img, score_threshold, timestamp=None, frame_idx=None, total_frames=None):
    """Add class legend and timestamp bar at the bottom of the image."""
    legend_h = 40
    canvas = np.zeros((img.shape[0] + legend_h, img.shape[1], 3), dtype=np.uint8)
    canvas[:img.shape[0]] = img
    canvas[img.shape[0]:] = (30, 30, 30)

    x_offset = 10
    for i, (name, color) in enumerate(zip(CLASS_NAMES, CLASS_COLORS_BGR)):
        cv2.rectangle(canvas, (x_offset, img.shape[0] + 8),
                      (x_offset + 20, img.shape[0] + 28), color, -1)
        cv2.putText(canvas, name, (x_offset + 25, img.shape[0] + 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA)
        x_offset += 25 + len(name) * 12 + 15

    right_text_parts = []
    if timestamp is not None:
        dt = datetime.datetime.fromtimestamp(timestamp)
        right_text_parts.append(dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])
    if frame_idx is not None and total_frames is not None:
        right_text_parts.append(f"[{frame_idx}/{total_frames}]")
    right_text_parts.append(f"score >= {score_threshold:.2f}")

    right_text = "  |  ".join(right_text_parts)
    text_size = cv2.getTextSize(right_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
    cv2.putText(canvas, right_text,
                (canvas.shape[1] - text_size[0] - 10, img.shape[0] + 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA)
    return canvas


def visualize_sample(token, detection, info, data_root, output_dir,
                     score_threshold=0.3, bev_range=54.0,
                     frame_idx=None, total_frames=None):
    """Visualize a single sample."""
    detections = parse_detections(detection, score_threshold)
    if len(detections) == 0:
        print(f"  [INFO] No detections above threshold for token {token[:8]}..., still generating visualization")
        # Continue with empty detections

    timestamp = info.get("timestamp")
    bev_img = draw_bev(detections, bev_range)

    cam_paths = info.get("all_cams_path", [])
    cam_extrinsics = info.get("all_cams_from_lidar", [])
    cam_intrinsics = info.get("all_cams_intrinsic", [])

    if len(cam_paths) != 6:
        print(f"  [WARN] Missing camera data for token {token[:8]}..., skipping camera views")
        front_imgs = [np.zeros((CAM_DISPLAY_H, CAM_DISPLAY_W, 3), dtype=np.uint8)] * 3
        back_imgs = [np.zeros((CAM_DISPLAY_H, CAM_DISPLAY_W, 3), dtype=np.uint8)] * 3
    else:
        resolved_cam_paths = []
        for p in cam_paths:
            if os.path.isabs(p):
                resolved_cam_paths.append(p)
            elif os.path.exists(p):
                resolved_cam_paths.append(p)
            else:
                resolved_cam_paths.append(os.path.join(data_root, p))

        front_imgs = []
        for idx, name in zip(FRONT_CAM_INDICES, FRONT_CAM_NAMES):
            img = draw_camera_image(
                resolved_cam_paths[idx], detections,
                cam_extrinsics[idx], cam_intrinsics[idx], name
            )
            front_imgs.append(img)

        back_imgs = []
        for idx, name in zip(BACK_CAM_INDICES, BACK_CAM_NAMES):
            img = draw_camera_image(
                resolved_cam_paths[idx], detections,
                cam_extrinsics[idx], cam_intrinsics[idx], name
            )
            back_imgs.append(img)

    result = compose_visualization(bev_img, front_imgs, back_imgs)
    result = add_legend(result, score_threshold,
                        timestamp=timestamp,
                        frame_idx=frame_idx,
                        total_frames=total_frames)

    prefix = f"{frame_idx:04d}_" if frame_idx is not None else ""
    out_path = os.path.join(output_dir, f"{prefix}{token}.jpg")
    cv2.imwrite(out_path, result, [cv2.IMWRITE_JPEG_QUALITY, 90])
    n_det = len(detections)
    ts_str = ""
    if timestamp is not None:
        dt = datetime.datetime.fromtimestamp(timestamp)
        ts_str = f"  ts={dt.strftime('%H:%M:%S.%f')[:-3]}"
    print(f"  Saved: {out_path}  ({n_det} detections){ts_str}")


def run_inference(cfg, checkpoint_path, max_samples=-1, tokens=None):
    """Build model, load weights, run inference on val set. Returns (predictions, infos_list)."""
    model = build_detector(cfg.model, train_cfg=None, test_cfg=cfg.test_cfg)
    print(f"Loading checkpoint from {checkpoint_path} ...")
    load_checkpoint(model, checkpoint_path, map_location="cpu")
    # Check if CUDA is available
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)
    model.eval()

    dataset = build_dataset(cfg.data.val)
    full_count = len(dataset._nusc_infos)

    if tokens is not None:
        target_set = set(tokens)
        dataset._nusc_infos = [
            info for info in dataset._nusc_infos if info["token"] in target_set
        ]
        print(f"Filtered dataset: {len(dataset._nusc_infos)}/{full_count} samples "
              f"matching {len(target_set)} target tokens")

    if max_samples > 0:
        dataset._nusc_infos = dataset._nusc_infos[:max_samples]

    workers = min(cfg.data.workers_per_gpu, len(dataset._nusc_infos))

    data_loader = build_dataloader(
        dataset,
        batch_size=1,
        workers_per_gpu=workers,
        dist=False,
        shuffle=False,
    )

    infos_list = dataset._nusc_infos

    predictions = {}
    cpu_device = torch.device("cpu")
    total = len(data_loader)

    print(f"Running inference on {total} samples ...")
    for i, data_batch in enumerate(data_loader):
        with torch.no_grad():
            outputs = batch_processor(model, data_batch, train_mode=False, local_rank=0)
        for output in outputs:
            token = output["metadata"]["token"]
            for k, v in output.items():
                if k != "metadata":
                    output[k] = v.to(cpu_device)
            predictions[token] = output

        if (i + 1) % 10 == 0 or i == total - 1:
            print(f"  [{i+1}/{total}]")

    print(f"  Inference done: {len(predictions)} predictions")
    return predictions, infos_list


def main():
    parser = argparse.ArgumentParser(description="Visualize CenterPoint detection results")

    parser.add_argument("--config", default=None,
                        help="Model config file path")
    parser.add_argument("--checkpoint", default=None,
                        help="Checkpoint (model weights) file path")

    parser.add_argument("--prediction", default=None,
                        help="Pre-computed prediction.pkl (skip inference)")
    parser.add_argument("--infos", default=None,
                        help="Path to infos_val_*.pkl (required when using --prediction)")
    parser.add_argument("--data-root", default="data/nuScenes",
                        help="nuScenes data root directory")

    parser.add_argument("--output-dir", default="vis_output",
                        help="Output directory for visualization images")
    parser.add_argument("--score-threshold", type=float, default=0.3,
                        help="Confidence score threshold")
    parser.add_argument("--bev-range", type=float, default=54.0,
                        help="BEV range in meters")
    parser.add_argument("--max-samples", type=int, default=-1,
                        help="Max samples to visualize (-1 for all)")
    parser.add_argument("--tokens", nargs="+", default=None,
                        help="Specific sample tokens to visualize")
    args = parser.parse_args()

    use_inference = args.config is not None and args.checkpoint is not None
    use_prediction = args.prediction is not None

    if not use_inference and not use_prediction:
        parser.error("Provide either (--config + --checkpoint) or --prediction")

    os.makedirs(args.output_dir, exist_ok=True)

    if use_inference:
        cfg = Config.fromfile(args.config)
        data_root = cfg.data_root if hasattr(cfg, "data_root") else args.data_root
        predictions, infos_list = run_inference(
            cfg, args.checkpoint,
            max_samples=args.max_samples, tokens=args.tokens,
        )
    else:
        if args.infos is None:
            parser.error("--infos is required when using --prediction")
        data_root = args.data_root

        print(f"Loading predictions from {args.prediction} ...")
        with open(args.prediction, "rb") as f:
            predictions = pickle.load(f)
        print(f"  Loaded {len(predictions)} samples")

        print(f"Loading infos from {args.infos} ...")
        with open(args.infos, "rb") as f:
            infos_list = pickle.load(f)
        print(f"  Loaded {len(infos_list)} infos")

    token_to_info = {info["token"]: info for info in infos_list}

    if args.tokens:
        tokens = args.tokens
    else:
        tokens = list(predictions.keys())
        if args.max_samples > 0:
            tokens = tokens[:args.max_samples]

    tokens = sorted(
        tokens,
        key=lambda t: token_to_info[t].get("timestamp", 0) if t in token_to_info else 0,
    )

    total_frames = len(tokens)
    print(f"\nVisualizing {total_frames} samples (score >= {args.score_threshold}) ...")
    for i, token in enumerate(tokens):
        print(f"[{i+1}/{total_frames}] Token: {token[:16]}...")

        if token not in predictions:
            print(f"  [SKIP] Token not in predictions")
            continue
        if token not in token_to_info:
            print(f"  [SKIP] Token not in infos")
            continue

        visualize_sample(
            token, predictions[token], token_to_info[token],
            data_root, args.output_dir,
            args.score_threshold, args.bev_range,
            frame_idx=i + 1, total_frames=total_frames,
        )

    print(f"\nDone! Results saved to {args.output_dir}/")


if __name__ == "__main__":
    main()
