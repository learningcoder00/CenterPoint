"""
Visualize CenterPoint detection results:
  - bev_cameras    : Center BEV (with boxes) + 6 cameras (with boxes)
  - forward_points : Virtual forward-looking point cloud + boxes
  - bev_compare    : Two BEVs (config A vs config B, both with boxes) +
                     3 forward / 3 backward cameras WITHOUT boxes

Usage (config + checkpoint, runs inference internally):
    python tools/visualize_results.py \
        --config configs/nusc_centerpoint_voxelnet_0075voxel_fix_bn_z.py \
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

Usage (A vs B compare visualization):
    python tools/visualize_results.py \
        --visualization-mode bev_compare \
        --config configs/A.py    --checkpoint work_dirs/A/epoch_20.pth \
        --config-b configs/B.py  --checkpoint-b work_dirs/B/epoch_20.pth \
        --output-dir vis_compare \
        --tokens TOKEN1 TOKEN2 ...
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
POINT_VIEW_W = 1600
POINT_VIEW_H = 900

# Forward-view coordinate convention requested by the UI:
#   x: vehicle forward, y: vehicle left/right, z: up.
# The raw lidar frame used by this dataset is right-forward-up in this view path,
# so convert raw xyz -> visualization xyz before filtering/projecting.
RAW_LIDAR_TO_FORWARD_VIEW = np.array([
    [0.0, 1.0, 0.0],
    [-1.0, 0.0, 0.0],
    [0.0, 0.0, 1.0],
], dtype=np.float32)


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


def draw_bev(detections, bev_range=54.0, title=None):
    """Draw BEV image with detection boxes only.

    title: optional caption rendered at the top of the BEV (e.g. "A: configs/x.py").
    """
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

    if title:
        # Draw a translucent banner so the title is readable on top of the BEV.
        banner_h = 64
        banner = img[:banner_h].copy()
        overlay = np.full_like(banner, (15, 15, 15))
        img[:banner_h] = cv2.addWeighted(banner, 0.35, overlay, 0.65, 0)
        cv2.putText(img, title, (24, 44),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.1, (245, 245, 245), 2, cv2.LINE_AA)

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


def draw_camera_image(img_path, detections, extrinsic, intrinsic, cam_name,
                      draw_boxes=True):
    """Load camera image and (optionally) draw projected 3D boxes.

    When ``draw_boxes`` is False the camera image is rendered as a clean context
    panel (used by the bev_compare layout where boxes only live on the BEVs).
    """
    img = cv2.imread(img_path)
    if img is None:
        img = np.zeros((900, 1600, 3), dtype=np.uint8)
        cv2.putText(img, f"Image not found: {cam_name}", (50, 450),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
        return cv2.resize(img, (CAM_DISPLAY_W, CAM_DISPLAY_H))

    h, w = img.shape[:2]

    if draw_boxes:
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


def compose_visualization_compare(bev_img_a, bev_img_b, front_imgs, back_imgs):
    """
    A vs B compare layout (cameras WITHOUT boxes, both BEVs WITH boxes):
      [front_left ]                          [back_left  ]
      [front      ]  [ BEV_A ] [ BEV_B ]    [back       ]
      [front_right]                          [back_right ]

    Both BEVs are resized to a square whose side equals the camera column
    height, so the whole canvas keeps a single height (3 cameras stacked).
    """
    left_col = np.vstack(front_imgs)
    right_col = np.vstack(back_imgs)
    cam_h = left_col.shape[0]

    bev_a = cv2.resize(bev_img_a, (cam_h, cam_h))
    bev_b = cv2.resize(bev_img_b, (cam_h, cam_h))
    divider = np.full((cam_h, 6, 3), 255, dtype=np.uint8)

    canvas = np.hstack([left_col, bev_a, divider, bev_b, right_col])
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


def resolve_data_path(path, data_root):
    if not path:
        return None
    if os.path.isabs(path) or os.path.exists(path):
        return path
    return os.path.join(data_root, path)


def load_lidar_points(info, data_root):
    lidar_path = resolve_data_path(info.get("lidar_path"), data_root)
    if not lidar_path or not os.path.exists(lidar_path):
        return None, lidar_path
    points = np.fromfile(lidar_path, dtype=np.float32)
    if points.size % 5 == 0:
        return points.reshape(-1, 5), lidar_path
    if points.size % 4 == 0:
        return points.reshape(-1, 4), lidar_path
    raise ValueError(f"Unsupported lidar point format: {lidar_path}, values={points.size}")


def transform_points_to_forward_view(points):
    if points is None:
        return None
    transformed = points.copy()
    transformed[:, :3] = points[:, :3] @ RAW_LIDAR_TO_FORWARD_VIEW.T
    return transformed


def transform_corners_to_forward_view(corners):
    return RAW_LIDAR_TO_FORWARD_VIEW @ corners


def virtual_forward_camera(camera_height=1.5, focal=820.0):
    """
    Virtual camera extrinsic/intrinsic for lidar-frame projection.
    Camera center is at lidar-frame (0, 0, camera_height), looking along lidar +x.
    """
    lidar_to_cam = np.array([
        [0.0, -1.0,  0.0, 0.0],
        [0.0,  0.0, -1.0, camera_height],
        [1.0,  0.0,  0.0, 0.0],
        [0.0,  0.0,  0.0, 1.0],
    ], dtype=np.float32)
    intrinsic = np.array([
        [focal, 0.0, POINT_VIEW_W / 2],
        [0.0, focal, POINT_VIEW_H * 0.58],
        [0.0, 0.0, 1.0],
    ], dtype=np.float32)
    return lidar_to_cam, intrinsic


def project_lidar_points_to_virtual_camera(points, lidar_to_cam, intrinsic, x_range=(0.0, 40.0), y_range=(-20.0, 20.0)):
    xyz = points[:, :3].astype(np.float32)
    mask = (
        (xyz[:, 0] >= x_range[0]) & (xyz[:, 0] <= x_range[1]) &
        (xyz[:, 1] >= y_range[0]) & (xyz[:, 1] <= y_range[1])
    )
    xyz = xyz[mask]
    if xyz.size == 0:
        return np.empty((0,), dtype=np.float32), np.empty((0,), dtype=np.int32), np.empty((0,), dtype=np.int32)

    points_homo = np.hstack([xyz, np.ones((xyz.shape[0], 1), dtype=np.float32)])
    cam = (lidar_to_cam @ points_homo.T).T
    depth = cam[:, 2]
    valid = depth > 0.1
    cam = cam[valid]
    depth = depth[valid]
    if cam.size == 0:
        return np.empty((0,), dtype=np.float32), np.empty((0,), dtype=np.int32), np.empty((0,), dtype=np.int32)

    uvw = (intrinsic @ cam[:, :3].T).T
    u = (uvw[:, 0] / uvw[:, 2]).astype(np.int32)
    v = (uvw[:, 1] / uvw[:, 2]).astype(np.int32)
    in_img = (u >= 0) & (u < POINT_VIEW_W) & (v >= 0) & (v < POINT_VIEW_H)
    return depth[in_img], u[in_img], v[in_img]


def draw_forward_boxes(img, detections, lidar_to_cam, intrinsic, transform_to_forward_view=False):
    for center, wlh, quat, label, score in detections:
        corners = corners_3d_box(center, wlh, quat)
        if transform_to_forward_view:
            corners = transform_corners_to_forward_view(corners)
        corners_2d = project_box_to_image(corners, lidar_to_cam, intrinsic, POINT_VIEW_W, POINT_VIEW_H)
        if corners_2d is None:
            continue
        color = CLASS_COLORS_BGR[label % len(CLASS_COLORS_BGR)]
        draw_3d_box_on_image(img, corners_2d, color, linewidth=3)
        valid = corners_2d[~np.isnan(corners_2d).any(axis=1)]
        if len(valid) > 0:
            anchor = valid.mean(axis=0).astype(int)
            text = f"{CLASS_NAMES[label % len(CLASS_NAMES)]} {score:.2f}"
            cv2.putText(img, text, (anchor[0] + 4, anchor[1] - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)


def draw_forward_pointcloud(points, detections=None, timestamp=None, frame_idx=None, total_frames=None,
                            x_range=(0.0, 40.0), y_range=(-20.0, 20.0), camera_height=1.5):
    """Render lidar points and predicted 3D boxes through a virtual forward-looking camera."""
    img = np.zeros((POINT_VIEW_H, POINT_VIEW_W, 3), dtype=np.uint8)
    img[:] = (8, 10, 18)
    lidar_to_cam, intrinsic = virtual_forward_camera(camera_height=camera_height)
    points = transform_points_to_forward_view(points)

    if points is None or len(points) == 0:
        cv2.putText(img, "No lidar points", (50, POINT_VIEW_H // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (180, 180, 180), 2, cv2.LINE_AA)
        draw_forward_boxes(img, detections or [], lidar_to_cam, intrinsic, transform_to_forward_view=True)
        return add_pointcloud_overlay(img, timestamp, frame_idx, total_frames, x_range=x_range, y_range=y_range)

    depth, u, v = project_lidar_points_to_virtual_camera(points, lidar_to_cam, intrinsic, x_range=x_range, y_range=y_range)
    if depth.size == 0:
        cv2.putText(img, "No lidar points in x[0,40], y[-20,20]", (50, POINT_VIEW_H // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (180, 180, 180), 2, cv2.LINE_AA)
        draw_forward_boxes(img, detections or [], lidar_to_cam, intrinsic, transform_to_forward_view=True)
        return add_pointcloud_overlay(img, timestamp, frame_idx, total_frames, x_range=x_range, y_range=y_range)

    if depth.size:
        order = np.argsort(-depth)  # draw far points first, near points last
        norm = np.clip((depth - x_range[0]) / max(x_range[1] - x_range[0], 1e-6), 0, 1)
        colors = cv2.applyColorMap((255 * (1 - norm)).astype(np.uint8), cv2.COLORMAP_TURBO)[:, 0, :]
        for idx in order:
            radius = 1 if depth[idx] > 25 else 2
            cv2.circle(img, (int(u[idx]), int(v[idx])), radius,
                       tuple(int(c) for c in colors[idx]), -1, cv2.LINE_AA)

    draw_forward_boxes(img, detections or [], lidar_to_cam, intrinsic, transform_to_forward_view=True)

    # Horizon and ego/camera marker.
    horizon_y = int(intrinsic[1, 2])
    horizon_x = int(intrinsic[0, 2])
    cv2.line(img, (0, horizon_y), (POINT_VIEW_W, horizon_y), (45, 55, 75), 1, cv2.LINE_AA)
    cv2.circle(img, (horizon_x, horizon_y), 5, (255, 255, 255), -1, cv2.LINE_AA)
    return add_pointcloud_overlay(img, timestamp, frame_idx, total_frames, x_range=x_range, y_range=y_range)


def add_pointcloud_overlay(img, timestamp=None, frame_idx=None, total_frames=None,
                           x_range=(0.0, 40.0), y_range=(-20.0, 20.0)):
    cv2.putText(img, "Virtual camera: position (0, 0, 1.5), looking forward (+x / vehicle front)",
                (24, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (235, 240, 255), 2, cv2.LINE_AA)
    cv2.putText(img, f"Points filtered to x[{x_range[0]:.0f},{x_range[1]:.0f}], y[{y_range[0]:.0f},{y_range[1]:.0f}]; color by x distance",
                (24, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (190, 205, 230), 1, cv2.LINE_AA)

    bar_x, bar_y, bar_w, bar_h = 24, POINT_VIEW_H - 58, 320, 16
    grad = np.linspace(255, 0, bar_w, dtype=np.uint8)[None, :]
    grad_img = cv2.applyColorMap(grad, cv2.COLORMAP_TURBO)
    img[bar_y:bar_y + bar_h, bar_x:bar_x + bar_w] = grad_img
    cv2.rectangle(img, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (220, 220, 220), 1)
    cv2.putText(img, f"{x_range[0]:.0f}m", (bar_x, bar_y - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1)
    cv2.putText(img, f"{x_range[1]:.0f}m", (bar_x + bar_w - 42, bar_y - 6),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1)

    right_text_parts = []
    if timestamp is not None:
        dt = datetime.datetime.fromtimestamp(timestamp)
        right_text_parts.append(dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])
    if frame_idx is not None and total_frames is not None:
        right_text_parts.append(f"[{frame_idx}/{total_frames}]")
    right_text = "  |  ".join(right_text_parts)
    if right_text:
        text_size = cv2.getTextSize(right_text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)[0]
        cv2.putText(img, right_text, (POINT_VIEW_W - text_size[0] - 24, POINT_VIEW_H - 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1, cv2.LINE_AA)
    return img


def _resolve_cam_paths(cam_paths, data_root):
    out = []
    for p in cam_paths:
        if os.path.isabs(p) or os.path.exists(p):
            out.append(p)
        else:
            out.append(os.path.join(data_root, p))
    return out


def _build_camera_columns(info, data_root, detections, draw_boxes):
    """Return (front_imgs, back_imgs) lists of 3 panels each."""
    cam_paths = info.get("all_cams_path", [])
    cam_extrinsics = info.get("all_cams_from_lidar", [])
    cam_intrinsics = info.get("all_cams_intrinsic", [])

    if len(cam_paths) != 6:
        empty = [np.zeros((CAM_DISPLAY_H, CAM_DISPLAY_W, 3), dtype=np.uint8)] * 3
        return list(empty), list(empty)

    resolved = _resolve_cam_paths(cam_paths, data_root)

    front_imgs = []
    for idx, name in zip(FRONT_CAM_INDICES, FRONT_CAM_NAMES):
        img = draw_camera_image(
            resolved[idx], detections,
            cam_extrinsics[idx], cam_intrinsics[idx], name,
            draw_boxes=draw_boxes,
        )
        front_imgs.append(img)

    back_imgs = []
    for idx, name in zip(BACK_CAM_INDICES, BACK_CAM_NAMES):
        img = draw_camera_image(
            resolved[idx], detections,
            cam_extrinsics[idx], cam_intrinsics[idx], name,
            draw_boxes=draw_boxes,
        )
        back_imgs.append(img)

    return front_imgs, back_imgs


def visualize_sample(token, detection, info, data_root, output_dir,
                     score_threshold=0.3, bev_range=54.0,
                     frame_idx=None, total_frames=None,
                     visualization_mode="bev_cameras",
                     detection_b=None,
                     bev_titles=None):
    """Visualize a single sample.

    detection_b / bev_titles are only used by visualization_mode=='bev_compare'.
    bev_titles is a tuple ``(title_a, title_b)`` rendered on top of each BEV.
    """
    detections = parse_detections(detection, score_threshold)
    if len(detections) == 0:
        print(f"  [INFO] No detections above threshold for token {token[:8]}..., still generating visualization")
        # Continue with empty detections

    timestamp = info.get("timestamp")

    if visualization_mode == "forward_points":
        points, lidar_path = load_lidar_points(info, data_root)
        if points is None:
            print(f"  [WARN] Missing lidar data for token {token[:8]}... path={lidar_path}")
        result = draw_forward_pointcloud(
            points, detections=detections, timestamp=timestamp,
            frame_idx=frame_idx, total_frames=total_frames)
        prefix = f"{frame_idx:04d}_" if frame_idx is not None else ""
        out_path = os.path.join(output_dir, f"{prefix}{token}.jpg")
        cv2.imwrite(out_path, result, [cv2.IMWRITE_JPEG_QUALITY, 92])
        print(f"  Saved: {out_path}  (forward point cloud)")
        return

    if visualization_mode == "bev_compare":
        if detection_b is None:
            raise ValueError("bev_compare mode requires detection_b for the same token")
        detections_b = parse_detections(detection_b, score_threshold)

        base_title_a, base_title_b = (bev_titles or ("A", "B"))
        # Append per-frame detection counts so visual diff is obvious at a glance.
        # Note: cv2.putText (Hershey font) only renders ASCII; non-ASCII separators
        # like U+00B7 render as "??", so keep this string in plain ASCII.
        title_a = f"{base_title_a}  |  {len(detections)} dets"
        title_b = f"{base_title_b}  |  {len(detections_b)} dets"
        bev_a = draw_bev(detections, bev_range, title=title_a)
        bev_b = draw_bev(detections_b, bev_range, title=title_b)

        # Cameras without boxes (clean context panels).
        front_imgs, back_imgs = _build_camera_columns(
            info, data_root, detections, draw_boxes=False
        )
        result = compose_visualization_compare(bev_a, bev_b, front_imgs, back_imgs)
        result = add_legend(result, score_threshold,
                            timestamp=timestamp,
                            frame_idx=frame_idx,
                            total_frames=total_frames)
        prefix = f"{frame_idx:04d}_" if frame_idx is not None else ""
        out_path = os.path.join(output_dir, f"{prefix}{token}.jpg")
        cv2.imwrite(out_path, result, [cv2.IMWRITE_JPEG_QUALITY, 90])
        ts_str = ""
        if timestamp is not None:
            dt = datetime.datetime.fromtimestamp(timestamp)
            ts_str = f"  ts={dt.strftime('%H:%M:%S.%f')[:-3]}"
        print(f"  Saved: {out_path}  (A:{len(detections)} / B:{len(detections_b)} dets){ts_str}")
        return

    bev_img = draw_bev(detections, bev_range)

    front_imgs, back_imgs = _build_camera_columns(
        info, data_root, detections, draw_boxes=True
    )

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


def _ensure_mini_infos_pkl(tokens, cache_dir, dataroot, version="v1.0-trainval",
                           nsweeps=10, filter_zero=True):
    """Build (or reuse) a per-clip mini infos pkl for the given sample tokens.

    Cache key = SHA1 of sorted tokens. If the cached pkl exists, skip the heavy
    nuScenes devkit load and just return its path. Otherwise call
    `nusc_common.create_mini_val_infos` to build it (~2-3 min cold cost mostly
    dominated by reading nuScenes JSON metadata tables; the per-token work
    itself is fractions of a second).
    """
    import hashlib
    os.makedirs(cache_dir, exist_ok=True)
    key = hashlib.sha1("\n".join(sorted(tokens)).encode("utf-8")).hexdigest()[:12]
    pkl_path = os.path.join(cache_dir, f"mini_infos_{key}.pkl")
    if os.path.exists(pkl_path):
        print(f"[mini_infos] cache hit: {pkl_path} ({len(tokens)} tokens)")
        return pkl_path
    print(f"[mini_infos] cache miss; building mini pkl for {len(tokens)} tokens "
          f"(dataroot={dataroot}, version={version}) ...")
    from det3d.datasets.nuscenes.nusc_common import create_mini_val_infos
    create_mini_val_infos(
        root_path=dataroot,
        sample_tokens=tokens,
        output_path=pkl_path,
        version=version,
        nsweeps=nsweeps,
        filter_zero=filter_zero,
    )
    return pkl_path


def run_inference(cfg, checkpoint_path, max_samples=-1, tokens=None):
    """Build model, load weights, run inference on val set. Returns (predictions, infos_list)."""
    if not cfg.test_cfg.get("circular_nms", False):
        try:
            import det3d.ops.iou3d_nms.iou3d_nms_cuda  # noqa: F401
        except ImportError:
            print("[WARN] iou3d CUDA extension unavailable; falling back to circle NMS")
            cfg.test_cfg.circular_nms = True
            cfg.test_cfg.min_radius = [4, 12, 10, 1, 0.85, 0.175]

    model = build_detector(cfg.model, train_cfg=None, test_cfg=cfg.test_cfg)
    print(f"Loading checkpoint from {checkpoint_path} ...")
    load_checkpoint(model, checkpoint_path, map_location="cpu")
    # Check if CUDA is available
    force_cpu = os.environ.get("CENTERPOINT_FORCE_CPU", "").lower() in {"1", "true", "yes"}
    device = torch.device("cpu" if force_cpu or not torch.cuda.is_available() else "cuda")
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
            outputs = batch_processor(model, data_batch, train_mode=False, device=device)
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
                        help="Model config file path (side A in bev_compare mode)")
    parser.add_argument("--checkpoint", default=None,
                        help="Checkpoint file path (side A in bev_compare mode)")

    parser.add_argument("--config-b", default=None,
                        help="Side-B config (only used when --visualization-mode=bev_compare)")
    parser.add_argument("--checkpoint-b", default=None,
                        help="Side-B checkpoint (only used when --visualization-mode=bev_compare)")

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
    parser.add_argument("--visualization-mode", default="bev_cameras",
                        choices=["bev_cameras", "forward_points", "bev_compare"],
                        help="Visualization layout: BEV+6 cameras, forward point cloud, or A/B BEV compare")

    parser.add_argument("--mini-infos-cache", default=None,
                        help=("Directory for on-the-fly per-clip mini infos pkls. When set + "
                              "--tokens given, the script builds (and caches by token-set hash) "
                              "a minimal infos pkl using nuScenes devkit, then overrides "
                              "cfg.data.val.info_path with it. Avoids the full ~50-min "
                              "infos_val_*.pkl build when you only need a handful of frames."))
    parser.add_argument("--nusc-version", default="v1.0-trainval",
                        help="nuScenes devkit version used when --mini-infos-cache is active.")
    parser.add_argument("--nusc-dataroot", default=None,
                        help=("nuScenes dataroot used when --mini-infos-cache is active. "
                              "Defaults to cfg.data_root or --data-root."))
    args = parser.parse_args()

    use_inference = args.config is not None and args.checkpoint is not None
    use_prediction = args.prediction is not None
    is_compare = args.visualization_mode == "bev_compare"

    if not use_inference and not use_prediction:
        parser.error("Provide either (--config + --checkpoint) or --prediction")

    if is_compare:
        if not use_inference:
            parser.error("bev_compare mode requires running inference; "
                         "pass --config/--checkpoint and --config-b/--checkpoint-b")
        if not args.config_b or not args.checkpoint_b:
            parser.error("bev_compare mode requires --config-b and --checkpoint-b")

    os.makedirs(args.output_dir, exist_ok=True)

    predictions_b = None
    bev_titles = None

    if use_inference:
        cfg = Config.fromfile(args.config)
        data_root = cfg.data_root if hasattr(cfg, "data_root") else args.data_root

        if args.mini_infos_cache and args.tokens:
            mini_pkl = _ensure_mini_infos_pkl(
                tokens=args.tokens,
                cache_dir=args.mini_infos_cache,
                dataroot=args.nusc_dataroot or data_root,
                version=args.nusc_version,
            )
            cfg.data.val.info_path = mini_pkl
            print(f"[mini_infos] cfg.data.val.info_path -> {mini_pkl}")

        predictions, infos_list = run_inference(
            cfg, args.checkpoint,
            max_samples=args.max_samples, tokens=args.tokens,
        )

        if is_compare:
            cfg_b = Config.fromfile(args.config_b)
            if args.mini_infos_cache and args.tokens:
                cfg_b.data.val.info_path = cfg.data.val.info_path
                print(f"[mini_infos] cfg_b.data.val.info_path -> {cfg_b.data.val.info_path}")
            print("\n[bev_compare] Running side-B inference ...")
            predictions_b, _infos_b = run_inference(
                cfg_b, args.checkpoint_b,
                max_samples=args.max_samples, tokens=args.tokens,
            )
            bev_titles = (
                f"A: {os.path.basename(args.config)}",
                f"B: {os.path.basename(args.config_b)}",
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
    print(f"Visualization mode: {args.visualization_mode}")
    for i, token in enumerate(tokens):
        print(f"[{i+1}/{total_frames}] Token: {token[:16]}...")

        if token not in predictions:
            print(f"  [SKIP] Token not in predictions")
            continue
        if token not in token_to_info:
            print(f"  [SKIP] Token not in infos")
            continue
        if is_compare and token not in predictions_b:
            print(f"  [SKIP] Token not in side-B predictions")
            continue

        visualize_sample(
            token, predictions[token], token_to_info[token],
            data_root, args.output_dir,
            args.score_threshold, args.bev_range,
            frame_idx=i + 1, total_frames=total_frames,
            visualization_mode=args.visualization_mode,
            detection_b=predictions_b[token] if is_compare else None,
            bev_titles=bev_titles,
        )

    print(f"\nDone! Results saved to {args.output_dir}/")


if __name__ == "__main__":
    main()
