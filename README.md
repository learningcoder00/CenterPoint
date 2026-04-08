# CenterPoint Clip Visualization Web UI

A full-stack clip preview and annotation tool built on [CenterPoint](https://arxiv.org/abs/2006.11275).  
Browse nuScenes clips, tag them, and launch BEV+camera visualization jobs directly from the browser.

---

## What you need before starting

| Item | Notes |
|------|-------|
| This repository | cloned locally |
| nuScenes dataset | `samples/`, `sweeps/`, `maps/`, and either `v1.0-trainval/` or `v1.0-test/` metadata must be on disk |
| A trained checkpoint | `.pth` file (only required when submitting visualization jobs) |

---

## 1. Environment setup

### 1.1 System packages

```bash
# Ubuntu 20.04 / 22.04
apt-get install -y openjdk-17-jdk maven ffmpeg
```

| Package | Why |
|---------|-----|
| `openjdk-17-jdk` | Spring Boot backend |
| `maven` | build the Java backend (first time only) |
| `ffmpeg` | stitch JPG frames into MP4 |

### 1.2 Python environment

```bash
conda create -n centerpoint python=3.8 -y
conda activate centerpoint

# PyTorch — pick the version matching your CUDA
# Example for CUDA 11.1:
conda install pytorch==1.9.0 torchvision==0.10.0 cudatoolkit=11.1 -c pytorch -c nvidia

# Project dependencies
pip install -r requirements.txt
pip install nuscenes-devkit==1.0.5
```

> **Note:** `spconv` is required for the VoxelNet model. Install the version that matches your CUDA:
> ```bash
> # CUDA 11.x:
> pip install spconv-cu111
> # or build from source: https://github.com/traveller59/spconv
> ```

### 1.3 Build CUDA extensions

```bash
cd det3d/ops/dcn && python setup.py build_ext --inplace && cd ../../..
cd det3d/ops/iou3d_nms && python setup.py build_ext --inplace && cd ../..
```

---

## 2. Dataset layout

Link or copy the nuScenes data so it is accessible under `data/nuScenes/`:

```bash
# Option A — symlink to an existing dataset mount
ln -s /path/to/nuscenes data/nuScenes

# Option B — the directory is already in place
# Just make sure data/nuScenes/ contains at minimum:
#   samples/   sweeps/   maps/   v1.0-trainval/  (or v1.0-test/)
```

Expected directory structure:

```
data/nuScenes/
├── samples/          # raw sensor data (LIDAR_TOP, CAM_FRONT, …)
│   ├── LIDAR_TOP/
│   ├── CAM_FRONT/
│   └── …
├── sweeps/           # intermediate LiDAR sweeps
├── maps/             # HD maps
├── v1.0-trainval/    # JSON metadata for train + val split
│   ├── sample.json
│   ├── sample_data.json
│   ├── calibrated_sensor.json
│   ├── ego_pose.json
│   └── …
└── v1.0-test/        # JSON metadata for test split (if using test data)
    └── …
```

> If you only have the **test split**, replace `v1.0-trainval` with `v1.0-test` everywhere below.

---

## 3. Generate the infos pickle

The infos pickle indexes all samples with their LiDAR paths, camera paths, calibration matrices, and sweep transforms. It is the single pre-processing step required before running the web UI.

```bash
# Using the existing script (trainval → val split, 10 sweeps, filter empty annotations)
PYTHONPATH=. python tools/create_data.py nuscenes_data_prep \
    --root_path data/nuScenes \
    --version   v1.0-trainval \
    --nsweeps   10

# Output: data/nuScenes/infos_val_10sweeps_withvelo_filter_True.pkl
#         data/nuScenes/infos_train_10sweeps_withvelo_filter_True.pkl
```

For the **test split** specifically, use the dedicated script:

```bash
PYTHONPATH=. python tools/create_nusc_test_infos.py \
    --data-root data/nuScenes \
    --version   v1.0-test \
    --output    data/nuScenes/infos_test_10sweeps_withvelo.pkl
```

> This step takes ~10–30 minutes depending on dataset size. Run it once; results are cached.

---

## 4. Generate clip metadata for the web UI

The web UI needs `clip_preview/clips_meta.json` — a lightweight index that groups samples into sequential clips and stores thumbnail paths.

```bash
# Using the val infos (trainval split):
PYTHONPATH=. python tools/generate_clip_preview.py \
    --infos data/nuScenes/infos_val_10sweeps_withvelo_filter_True.pkl

# Or using the test infos:
PYTHONPATH=. python tools/generate_clip_preview.py \
    --infos data/nuScenes/infos_test_10sweeps_withvelo.pkl
```

Output: `clip_preview/clips_meta.json` (~150 clips by default).

> `start_server.sh` runs this step automatically if `clips_meta.json` is missing.

---

## 5. Build the Java backend (first time only)

```bash
cd backend
mvn package -DskipTests
cd ..
# Output: backend/target/centerpoint-viz-1.0.0.jar
```

Only rebuild when Java source files change.

---

## 6. Start the server

### One-command launch (recommended)

```bash
bash start_server.sh \
    --config     configs/nusc/voxelnet/nusc_centerpoint_voxelnet_0075voxel_fix_bn_z.py \
    --checkpoint work_dirs/epoch_20.pth \
    --port       8081
```

The script will:
1. Check that `java`, `ffmpeg`, and `python` are on `PATH`
2. Auto-run `generate_clip_preview.py` if `clips_meta.json` is missing
3. Start the Java Spring Boot server

Open **http://127.0.0.1:8081/clips** in your browser.

### All options

```
--config     <path>        model config file
--checkpoint <path>        checkpoint weights (.pth)
--port       <port>        HTTP port (default: 8081)
--host       <addr>        bind address (default: 0.0.0.0)
--backend    java|python   server implementation (default: java)
```

### Manual start (without the shell script)

```bash
# Java backend
java -jar backend/target/centerpoint-viz-1.0.0.jar \
    --app.config=configs/nusc/voxelnet/nusc_centerpoint_voxelnet_0075voxel_fix_bn_z.py \
    --app.checkpoint=work_dirs/epoch_20.pth \
    --app.project-root=$(pwd) \
    --server.port=8081

# Python fallback backend
PYTHONPATH=. python tools/server.py \
    --config     configs/nusc/voxelnet/nusc_centerpoint_voxelnet_0075voxel_fix_bn_z.py \
    --checkpoint work_dirs/epoch_20.pth \
    --port       8081
```

---

## 7. Using the web UI

| Page | URL | What you can do |
|------|-----|-----------------|
| Clips | `http://127.0.0.1:8081/clips` | Browse clips, hover to preview frames, add/edit tags, search by clip ID or tag, select multiple clips |
| Results | `http://127.0.0.1:8081/results` | View submitted visualization jobs, monitor progress, play completed MP4 videos |

---

## Quick-start summary

```bash
# 1. Install system deps
apt-get install -y openjdk-17-jdk maven ffmpeg

# 2. Install Python deps
conda activate centerpoint
pip install -r requirements.txt nuscenes-devkit==1.0.5

# 3. Build CUDA extensions
cd det3d/ops/dcn && python setup.py build_ext --inplace && cd ../../..
cd det3d/ops/iou3d_nms && python setup.py build_ext --inplace && cd ../..

# 4. Link dataset
ln -s /path/to/nuscenes data/nuScenes

# 5. Generate infos pickle (one-time)
PYTHONPATH=. python tools/create_data.py nuscenes_data_prep \
    --root_path data/nuScenes --version v1.0-trainval --nsweeps 10

# 6. Build Java backend (one-time)
cd backend && mvn package -DskipTests && cd ..

# 7. Launch
bash start_server.sh \
    --config     configs/nusc/voxelnet/nusc_centerpoint_voxelnet_0075voxel_fix_bn_z.py \
    --checkpoint work_dirs/epoch_20.pth \
    --port       8081
```

---

## Project layout

```
CenterPoint/
├── backend/                          # Spring Boot 3 Java backend
│   ├── pom.xml
│   └── src/main/java/com/centerpoint/viz/
│       ├── controller/               # REST API (/api/clips, /api/jobs, /api/config)
│       ├── service/                  # ClipService, JobService, JobExecutor
│       └── repository/               # SQLite via JdbcTemplate
├── configs/nusc/voxelnet/            # model configs
├── det3d/                            # CenterPoint model + dataset code
├── tools/
│   ├── create_data.py                # generate infos pkl (trainval / test)
│   ├── create_nusc_test_infos.py     # generate infos pkl for test split
│   ├── generate_clip_preview.py      # generate clips_meta.json for the web UI
│   ├── visualize_results.py          # per-sample BEV + camera visualization
│   ├── server.py                     # Python FastAPI backend (fallback)
│   └── frontend-vue/                 # Vue 3 + Vite SPA
│       └── dist/                     # pre-built frontend (served by backend)
├── clip_preview/
│   └── clips_meta.json               # generated clip index
├── data/
│   └── nuScenes -> /path/to/dataset  # symlink or directory
├── work_dirs/
│   ├── clip_jobs.db                  # SQLite DB (jobs + tags)
│   └── vis_jobs/<job_id>/            # per-job output frames and MP4
└── start_server.sh                   # one-command launcher
```

---

## License

Released under the MIT License. See [LICENSE](LICENSE).
