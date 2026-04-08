#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# 一键启动 CenterPoint Clip 可视化服务
#
# 用法：
#   bash start_server.sh              # 使用默认配置
#   bash start_server.sh --port 8082  # 自定义端口
# ─────────────────────────────────────────────────────────────────────────────

set -e

# ── 路径定位 ──────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── 默认参数（可在此修改） ─────────────────────────────────────────────────────
CONFIG="configs/nusc/voxelnet/nusc_centerpoint_voxelnet_0075voxel_fix_bn_z.py"
CHECKPOINT="work_dirs/epoch_20.pth"
PORT=8081
HOST="0.0.0.0"
BACKEND="java"   # "java" 或 "python"

# ── 解析命令行参数 ─────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)     CONFIG="$2";     shift 2 ;;
    --checkpoint) CHECKPOINT="$2"; shift 2 ;;
    --port)       PORT="$2";       shift 2 ;;
    --host)       HOST="$2";       shift 2 ;;
    --backend)    BACKEND="$2";    shift 2 ;;
    -h|--help)
      echo "用法: bash start_server.sh [选项]"
      echo "  --config     <路径>   模型 config 文件（默认: $CONFIG）"
      echo "  --checkpoint <路径>   权重文件（默认: $CHECKPOINT）"
      echo "  --port       <端口>   服务端口（默认: $PORT）"
      echo "  --host       <主机>   绑定主机（默认: $HOST）"
      echo "  --backend    java|python  使用的后端（默认: java）"
      exit 0 ;;
    *) echo "未知选项: $1"; exit 1 ;;
  esac
done

# ── 颜色输出 ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'

echo -e "${CYAN}=====================================================${NC}"
echo -e "${CYAN}   CenterPoint Clip Visualization Server${NC}"
echo -e "${CYAN}=====================================================${NC}"

# ── 检查依赖 ──────────────────────────────────────────────────────────────────
echo -e "\n${YELLOW}[1/4] 检查依赖...${NC}"

if ! command -v python &>/dev/null; then
  echo -e "${RED}✗ python 未找到${NC}"; exit 1
fi
echo -e "  ${GREEN}✓ Python $(python --version 2>&1)${NC}"

if ! command -v ffmpeg &>/dev/null; then
  echo -e "${RED}✗ ffmpeg 未找到，请先安装: apt-get install -y ffmpeg${NC}"; exit 1
fi
echo -e "  ${GREEN}✓ ffmpeg$(NC) $(ffmpeg -version 2>&1 | head -1)"

if [ "$BACKEND" = "java" ]; then
  if ! command -v java &>/dev/null; then
    echo -e "${RED}✗ java 未找到，请先安装: apt-get install -y openjdk-17-jdk${NC}"; exit 1
  fi
  echo -e "  ${GREEN}✓ Java$(NC) $(java -version 2>&1 | head -1)"
  JAR="$SCRIPT_DIR/backend/target/centerpoint-viz-1.0.0.jar"
  if [ ! -f "$JAR" ]; then
    echo -e "${YELLOW}  JAR 不存在，正在构建...${NC}"
    cd "$SCRIPT_DIR/backend" && mvn package -DskipTests -q && cd "$SCRIPT_DIR"
    echo -e "  ${GREEN}✓ 构建完成${NC}"
  fi
  echo -e "  ${GREEN}✓ Java JAR: $JAR${NC}"
else
  python -c "import fastapi, uvicorn, aiosqlite" 2>/dev/null || {
    echo -e "${YELLOW}  安装缺失的 Python 依赖...${NC}"
    pip install fastapi uvicorn aiosqlite -q
  }
  echo -e "  ${GREEN}✓ Python 依赖已就绪${NC}"
fi

# ── 检查关键文件 ───────────────────────────────────────────────────────────────
echo -e "\n${YELLOW}[2/4] 检查文件...${NC}"

MISSING=0

if [ ! -f "$CONFIG" ]; then
  echo -e "  ${RED}✗ Config 不存在: $CONFIG${NC}"; MISSING=1
else
  echo -e "  ${GREEN}✓ Config:     $CONFIG${NC}"
fi

if [ ! -f "$CHECKPOINT" ]; then
  echo -e "  ${YELLOW}⚠ Checkpoint 不存在: $CHECKPOINT（可在页面提交时手动指定）${NC}"
else
  echo -e "  ${GREEN}✓ Checkpoint: $CHECKPOINT${NC}"
fi

if [ ! -f "clip_preview/clips_meta.json" ]; then
  echo -e "  ${YELLOW}⚠ clips_meta.json 不存在，正在生成...${NC}"
  PYTHONPATH="$SCRIPT_DIR" python tools/generate_clip_preview.py
  echo -e "  ${GREEN}✓ 已生成 clip_preview/clips_meta.json${NC}"
else
  CLIP_COUNT=$(python -c "import json; d=json.load(open('clip_preview/clips_meta.json')); print(d['total_clips'])" 2>/dev/null || echo "?")
  echo -e "  ${GREEN}✓ clips_meta.json（${CLIP_COUNT} clips）${NC}"
fi

if [ $MISSING -eq 1 ]; then
  echo -e "\n${RED}关键文件缺失，请检查后重试。${NC}"; exit 1
fi

# ── 检查端口占用 ───────────────────────────────────────────────────────────────
echo -e "\n${YELLOW}[3/4] 检查端口 $PORT...${NC}"
if lsof -i ":$PORT" &>/dev/null 2>&1; then
  echo -e "  ${YELLOW}⚠ 端口 $PORT 已被占用，尝试自动切换到 $((PORT+1))...${NC}"
  PORT=$((PORT+1))
  if lsof -i ":$PORT" &>/dev/null 2>&1; then
    echo -e "  ${RED}✗ 端口 $PORT 也被占用，请手动指定: bash start_server.sh --port <端口号>${NC}"; exit 1
  fi
fi
echo -e "  ${GREEN}✓ 端口 $PORT 可用${NC}"

# ── 启动服务 ───────────────────────────────────────────────────────────────────
echo -e "\n${YELLOW}[4/4] 启动服务...${NC}"
echo -e "  Config:     ${CYAN}$CONFIG${NC}"
echo -e "  Checkpoint: ${CYAN}$CHECKPOINT${NC}"
echo -e "  地址:       ${CYAN}http://127.0.0.1:$PORT${NC}"
echo -e "\n${GREEN}按 Ctrl+C 停止服务${NC}\n"

export PYTHONPATH="$SCRIPT_DIR:${PYTHONPATH:-}"

if [ "$BACKEND" = "java" ]; then
  exec java -jar "$SCRIPT_DIR/backend/target/centerpoint-viz-1.0.0.jar" \
    --app.config="$CONFIG" \
    --app.checkpoint="$CHECKPOINT" \
    --app.project-root="$SCRIPT_DIR" \
    --server.address="$HOST" \
    --server.port="$PORT"
else
  exec python tools/server.py \
    --config "$CONFIG" \
    --checkpoint "$CHECKPOINT" \
    --host "$HOST" \
    --port "$PORT"
fi
