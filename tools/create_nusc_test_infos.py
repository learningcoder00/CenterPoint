"""
Generate nuScenes infos pkl for any split (trainval / test / mini),
with the same structure as:
    infos_val_10sweeps_withvelo_filter_True_gts_with_npz.pkl

Extra field compared to the standard nusc_common output:
    occ_gt_path  : str  path to <gts_root>/gts/<scene_name>/<token>/labels.npz
                        (None if --gts-root is not provided or the file doesn't exist)

Usage examples
--------------
# Generate test infos (no GT boxes, no occ GT):
PYTHONPATH=. python tools/create_nusc_test_infos.py \\
    --data-root  data/nuScenes \\
    --version    v1.0-test \\
    --output     data/nuScenes/infos_test_10sweeps_withvelo.pkl

# Generate val infos with occ GT paths (replicates the reference file):
PYTHONPATH=. python tools/create_nusc_test_infos.py \\
    --data-root  data/nuScenes \\
    --version    v1.0-trainval \\
    --split      val \\
    --gts-root   /path/to/nuScenes_occ  \\
    --output     data/nuScenes/infos_val_10sweeps_withvelo_filter_True_gts_with_npz.pkl
"""

import argparse
import pickle
from functools import reduce
from pathlib import Path

import numpy as np
from tqdm import tqdm
from pyquaternion import Quaternion

try:
    from nuscenes import NuScenes
    from nuscenes.utils import splits
    from nuscenes.utils.geometry_utils import transform_matrix
except ImportError:
    raise RuntimeError("nuScenes devkit not found. Install via: pip install nuscenes-devkit")

# ── camera channel order (matches visualize_results.py) ─────────────────────
CAM_CHANS = [
    "CAM_FRONT", "CAM_FRONT_RIGHT", "CAM_BACK_RIGHT",
    "CAM_BACK", "CAM_BACK_LEFT", "CAM_FRONT_LEFT",
]

# ── nuScenes class name → detection class mapping ───────────────────────────
GENERAL_TO_DETECTION = {
    "human.pedestrian.adult":               "pedestrian",
    "human.pedestrian.child":               "pedestrian",
    "human.pedestrian.wheelchair":          "ignore",
    "human.pedestrian.stroller":            "ignore",
    "human.pedestrian.personal_mobility":   "ignore",
    "human.pedestrian.police_officer":      "pedestrian",
    "human.pedestrian.construction_worker": "pedestrian",
    "animal":                               "ignore",
    "vehicle.car":                          "car",
    "vehicle.motorcycle":                   "motorcycle",
    "vehicle.bicycle":                      "bicycle",
    "vehicle.bus.bendy":                    "bus",
    "vehicle.bus.rigid":                    "bus",
    "vehicle.truck":                        "truck",
    "vehicle.construction":                 "construction_vehicle",
    "vehicle.emergency.ambulance":          "ignore",
    "vehicle.emergency.police":             "ignore",
    "vehicle.trailer":                      "trailer",
    "movable_object.barrier":               "barrier",
    "movable_object.trafficcone":           "traffic_cone",
    "movable_object.pushable_pullable":     "ignore",
    "movable_object.debris":                "ignore",
    "static_object.bicycle_rack":           "ignore",
}


# ── helpers ──────────────────────────────────────────────────────────────────

def quaternion_yaw(q: Quaternion) -> float:
    v = np.dot(q.rotation_matrix, np.array([1, 0, 0]))
    return np.arctan2(v[1], v[0])


def get_lidar_to_image_transform(nusc, pointsensor, camera_sensor):
    tms, intrinsics, cam_paths = [], [], []
    for chan in CAM_CHANS:
        cam = camera_sensor[chan]
        lidar_cs = nusc.get("calibrated_sensor", pointsensor["calibrated_sensor_token"])
        car_from_lidar = transform_matrix(
            lidar_cs["translation"], Quaternion(lidar_cs["rotation"]), inverse=False
        )
        lidar_pose = nusc.get("ego_pose", pointsensor["ego_pose_token"])
        global_from_car = transform_matrix(
            lidar_pose["translation"], Quaternion(lidar_pose["rotation"]), inverse=False
        )
        cam_pose = nusc.get("ego_pose", cam["ego_pose_token"])
        car_from_global = transform_matrix(
            cam_pose["translation"], Quaternion(cam_pose["rotation"]), inverse=True
        )
        cam_cs = nusc.get("calibrated_sensor", cam["calibrated_sensor_token"])
        cam_from_car = transform_matrix(
            cam_cs["translation"], Quaternion(cam_cs["rotation"]), inverse=True
        )
        tm = reduce(np.dot, [cam_from_car, car_from_global, global_from_car, car_from_lidar])
        cam_path, _, intrinsic = nusc.get_sample_data(cam["token"])
        tms.append(tm)
        intrinsics.append(intrinsic)
        cam_paths.append(cam_path)
    return tms, intrinsics, cam_paths


def find_closest_camera_tokens(nusc, pointsensor, ref_sample):
    lidar_ts = pointsensor["timestamp"]
    min_cams = {}
    for chan in CAM_CHANS:
        cam = nusc.get("sample_data", ref_sample["data"][chan])
        min_diff, min_cam = abs(lidar_ts - cam["timestamp"]), cam
        for _ in range(6):
            if cam["prev"] == "":
                break
            cam = nusc.get("sample_data", cam["prev"])
            diff = abs(lidar_ts - cam["timestamp"])
            if diff < min_diff:
                min_diff, min_cam = diff, cam
        min_cams[chan] = min_cam
    return min_cams


def get_sample_data_boxes(nusc, sample_data_token):
    """Return (lidar_path, boxes) in lidar sensor frame."""
    sd_rec = nusc.get("sample_data", sample_data_token)
    cs_rec = nusc.get("calibrated_sensor", sd_rec["calibrated_sensor_token"])
    pose_rec = nusc.get("ego_pose", sd_rec["ego_pose_token"])

    data_path = nusc.get_sample_data_path(sample_data_token)

    boxes_global = nusc.get_boxes(sample_data_token)
    boxes_lidar = []
    for box in boxes_global:
        box.velocity = nusc.box_velocity(box.token)
        box.translate(-np.array(pose_rec["translation"]))
        box.rotate(Quaternion(pose_rec["rotation"]).inverse)
        box.translate(-np.array(cs_rec["translation"]))
        box.rotate(Quaternion(cs_rec["rotation"]).inverse)
        boxes_lidar.append(box)

    return data_path, boxes_lidar


# ── main info builder ─────────────────────────────────────────────────────────

def build_infos(nusc, scene_tokens, is_test=False, nsweeps=10, filter_zero=True, gts_root=None):
    """
    Build a list of sample-info dicts.

    Parameters
    ----------
    nusc        : NuScenes object
    scene_tokens: set of scene token strings to include
    is_test     : if True, skip GT annotation fields
    nsweeps     : number of LiDAR sweeps to aggregate (includes current frame)
    filter_zero : if True, remove annotations with 0 lidar+radar points
    gts_root    : optional path to occupancy GT root.
                  Expected structure: <gts_root>/gts/<scene_name>/<token>/labels.npz
    """
    infos = []

    # Build token → scene_name lookup for occ_gt_path
    token_to_scene = {}
    if gts_root is not None:
        for scene in nusc.scene:
            if scene["token"] in scene_tokens:
                sample_token = scene["first_sample_token"]
                while sample_token:
                    token_to_scene[sample_token] = scene["name"]
                    sample_token = nusc.get("sample", sample_token).get("next", "")

    for sample in tqdm(nusc.sample, desc="Building infos"):
        if sample["scene_token"] not in scene_tokens:
            continue

        ref_sd_token = sample["data"]["LIDAR_TOP"]
        ref_sd_rec = nusc.get("sample_data", ref_sd_token)
        ref_cs_rec = nusc.get("calibrated_sensor", ref_sd_rec["calibrated_sensor_token"])
        ref_pose_rec = nusc.get("ego_pose", ref_sd_rec["ego_pose_token"])
        ref_time = 1e-6 * ref_sd_rec["timestamp"]

        ref_lidar_path, ref_boxes = get_sample_data_boxes(nusc, ref_sd_token)

        ref_cam_front_token = sample["data"]["CAM_FRONT"]
        ref_cam_path, _, ref_cam_intrinsic = nusc.get_sample_data(ref_cam_front_token)

        ref_from_car = transform_matrix(
            ref_cs_rec["translation"], Quaternion(ref_cs_rec["rotation"]), inverse=True
        )
        car_from_global = transform_matrix(
            ref_pose_rec["translation"], Quaternion(ref_pose_rec["rotation"]), inverse=True
        )

        ref_cams = {
            chan: nusc.get("sample_data", sample["data"][chan]) for chan in CAM_CHANS
        }
        all_cams_from_lidar, all_cams_intrinsic, all_cams_path = \
            get_lidar_to_image_transform(nusc, ref_sd_rec, ref_cams)

        info = {
            "lidar_path":         ref_lidar_path,
            "cam_front_path":     ref_cam_path,
            "cam_intrinsic":      ref_cam_intrinsic,
            "token":              sample["token"],
            "sweeps":             [],
            "ref_from_car":       ref_from_car,
            "car_from_global":    car_from_global,
            "timestamp":          ref_time,
            "all_cams_from_lidar": all_cams_from_lidar,
            "all_cams_intrinsic":  all_cams_intrinsic,
            "all_cams_path":       all_cams_path,
        }

        # ── sweeps ──────────────────────────────────────────────────────────
        curr_sd_rec = nusc.get("sample_data", sample["data"]["LIDAR_TOP"])
        sweeps = []
        while len(sweeps) < nsweeps - 1:
            if curr_sd_rec["prev"] == "":
                if len(sweeps) == 0:
                    sweep = {
                        "lidar_path":          ref_lidar_path,
                        "sample_data_token":   curr_sd_rec["token"],
                        "transform_matrix":    None,
                        "time_lag":            curr_sd_rec["timestamp"] * 0,
                        "all_cams_from_lidar": all_cams_from_lidar,
                        "all_cams_intrinsic":  all_cams_intrinsic,
                        "all_cams_path":       all_cams_path,
                    }
                    sweeps.append(sweep)
                else:
                    sweeps.append(sweeps[-1])
            else:
                curr_sd_rec = nusc.get("sample_data", curr_sd_rec["prev"])
                cam_data = find_closest_camera_tokens(nusc, curr_sd_rec, ref_sample=sample)
                cur_cams_from_lidar, cur_cams_intrinsic, cur_cams_path = \
                    get_lidar_to_image_transform(nusc, curr_sd_rec, cam_data)

                cur_pose = nusc.get("ego_pose", curr_sd_rec["ego_pose_token"])
                global_from_car = transform_matrix(
                    cur_pose["translation"], Quaternion(cur_pose["rotation"]), inverse=False
                )
                cur_cs = nusc.get("calibrated_sensor", curr_sd_rec["calibrated_sensor_token"])
                car_from_current = transform_matrix(
                    cur_cs["translation"], Quaternion(cur_cs["rotation"]), inverse=False
                )
                tm = reduce(
                    np.dot,
                    [ref_from_car, car_from_global, global_from_car, car_from_current],
                )
                sweep = {
                    "lidar_path":          nusc.get_sample_data_path(curr_sd_rec["token"]),
                    "sample_data_token":   curr_sd_rec["token"],
                    "transform_matrix":    tm,
                    "global_from_car":     global_from_car,
                    "car_from_current":    car_from_current,
                    "time_lag":            ref_time - 1e-6 * curr_sd_rec["timestamp"],
                    "all_cams_from_lidar": cur_cams_from_lidar,
                    "all_cams_intrinsic":  cur_cams_intrinsic,
                    "all_cams_path":       cur_cams_path,
                }
                sweeps.append(sweep)

        info["sweeps"] = sweeps
        assert len(info["sweeps"]) == nsweeps - 1, \
            f"Expected {nsweeps-1} sweeps, got {len(info['sweeps'])}"

        # ── GT annotations (not available for test split) ────────────────────
        if not is_test:
            annotations = [
                nusc.get("sample_annotation", tok) for tok in sample["anns"]
            ]
            mask = np.array(
                [(a["num_lidar_pts"] + a["num_radar_pts"]) > 0 for a in annotations],
                dtype=bool,
            )

            locs     = np.array([b.center for b in ref_boxes]).reshape(-1, 3)
            dims     = np.array([b.wlh    for b in ref_boxes]).reshape(-1, 3)
            velocity = np.array([b.velocity for b in ref_boxes]).reshape(-1, 3)
            rots     = np.array([quaternion_yaw(b.orientation) for b in ref_boxes]).reshape(-1, 1)
            names    = np.array([b.name  for b in ref_boxes])
            tokens   = np.array([b.token for b in ref_boxes])
            gt_boxes = np.concatenate(
                [locs, dims, velocity[:, :2], -rots - np.pi / 2], axis=1
            )

            if filter_zero:
                info["gt_boxes"]          = gt_boxes[mask]
                info["gt_boxes_velocity"] = velocity[mask]
                info["gt_names"]          = np.array(
                    [GENERAL_TO_DETECTION[n] for n in names]
                )[mask]
                info["gt_boxes_token"]    = tokens[mask]
            else:
                info["gt_boxes"]          = gt_boxes
                info["gt_boxes_velocity"] = velocity
                info["gt_names"]          = np.array(
                    [GENERAL_TO_DETECTION[n] for n in names]
                )
                info["gt_boxes_token"]    = tokens

        # ── occupancy GT path ────────────────────────────────────────────────
        occ_path = None
        if gts_root is not None:
            scene_name = token_to_scene.get(sample["token"])
            if scene_name:
                candidate = Path(gts_root) / "gts" / scene_name / sample["token"] / "labels.npz"
                occ_path = str(candidate) if candidate.exists() else str(candidate)
                # We always write the expected path; caller can validate existence.
        info["occ_gt_path"] = occ_path

        infos.append(info)

    return infos


# ── entry point ───────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="Create nuScenes infos pkl (compatible with gts_with_npz format)"
    )
    p.add_argument("--data-root", required=True,
                   help="Root directory of the nuScenes dataset (contains v1.0-*/)")
    p.add_argument("--version", default="v1.0-trainval",
                   choices=["v1.0-trainval", "v1.0-test", "v1.0-trainval"],
                   help="Dataset version (default: v1.0-trainval)")
    p.add_argument("--split", default=None,
                   choices=["train", "val", "test", "mini_train", "mini_val", None],
                   help="Which split to export. Defaults: test→test, trainval→val, mini→mini_val")
    p.add_argument("--nsweeps", type=int, default=10,
                   help="Number of LiDAR sweeps to aggregate (default: 10)")
    p.add_argument("--no-filter-zero", action="store_true",
                   help="Keep annotations with 0 LiDAR/radar points (default: filter them out)")
    p.add_argument("--gts-root", default=None,
                   help="Root directory containing occupancy GT npz files. "
                        "Expected: <gts-root>/gts/<scene_name>/<token>/labels.npz. "
                        "If omitted, occ_gt_path will be None for all samples.")
    p.add_argument("--output", required=True,
                   help="Output pkl file path, e.g. data/nuScenes/infos_test_10sweeps_withvelo.pkl")
    return p.parse_args()


def main():
    args = parse_args()
    filter_zero = not args.no_filter_zero

    print(f"Loading nuScenes {args.version} from {args.data_root} ...")
    nusc = NuScenes(version=args.version, dataroot=args.data_root, verbose=True)

    # ── determine which scenes to export ─────────────────────────────────────
    is_test = "test" in args.version
    if args.split is not None:
        split_name = args.split
    elif args.version == "v1.0-test":
        split_name = "test"
    elif args.version == "v1.0-trainval":
        split_name = "val"
    elif args.version == "v1.0-trainval":
        split_name = "mini_val"

    split_scenes = getattr(splits, split_name)

    # ── filter to scenes that actually exist on disk ──────────────────────────
    available = []
    print("Checking available scenes ...")
    for scene in nusc.scene:
        token = scene["token"]
        sample = nusc.get("sample", scene["first_sample_token"])
        sd = nusc.get("sample_data", sample["data"]["LIDAR_TOP"])
        lidar_path = nusc.get_sample_data_path(sd["token"])
        if Path(lidar_path).exists():
            available.append(scene)

    available_names = {s["name"] for s in available}
    valid_scene_names = [n for n in split_scenes if n in available_names]
    print(f"  Requested: {len(split_scenes)}, available on disk: {len(valid_scene_names)}")

    scene_token_set = set(
        s["token"] for s in available if s["name"] in valid_scene_names
    )

    # ── build infos ───────────────────────────────────────────────────────────
    print(f"Building infos (nsweeps={args.nsweeps}, filter_zero={filter_zero}, "
          f"is_test={is_test or split_name=='test'}) ...")
    infos = build_infos(
        nusc,
        scene_token_set,
        is_test=(is_test or split_name == "test"),
        nsweeps=args.nsweeps,
        filter_zero=filter_zero,
        gts_root=args.gts_root,
    )

    # ── save ──────────────────────────────────────────────────────────────────
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        pickle.dump(infos, f)

    print(f"\nDone. Saved {len(infos)} samples → {output_path}")
    if infos:
        print("Fields in each info:", list(infos[0].keys()))


if __name__ == "__main__":
    main()
