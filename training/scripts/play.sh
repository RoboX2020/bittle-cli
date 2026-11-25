#!/usr/bin/env bash
# ==============================================================================
# Petoi Bittle Policy Playback & Visualization Script
# ==============================================================================

set -e

TERRAIN="flat"
NUM_ENVS=16
CHECKPOINT=""
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
  case $1 in
    --terrain|-t)
      TERRAIN="$2"
      shift 2
      ;;
    --num_envs|-n)
      NUM_ENVS="$2"
      shift 2
      ;;
    --checkpoint|-c)
      CHECKPOINT="$2"
      shift 2
      ;;
    --livestream)
      EXTRA_ARGS+=(--livestream "$2")
      shift 2
      ;;
    --viz)
      EXTRA_ARGS+=(--viz "$2")
      shift 2
      ;;
    --help|-h)
      echo "Usage: ./play.sh [options]"
      echo ""
      echo "Options:"
      echo "  -t, --terrain         Terrain type: 'flat' or 'rough' [default: flat]"
      echo "  -n, --num_envs        Number of environments to play [default: 16]"
      echo "  -c, --checkpoint      Path to policy checkpoint (.pt file) or 'latest'"
      echo "  --livestream [1|2]    Enable Omniverse WebRTC streaming"
      echo "  --viz kit             Enable interactive desktop GUI viewer"
      exit 0
      ;;
    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

TERRAIN_CAP="$(tr '[:lower:]' '[:upper:]' <<< "${TERRAIN:0:1}")${TERRAIN:1}"
TASK="Isaac-Velocity-${TERRAIN_CAP}-Bittle"

export PATH="/home/robotics/.local/bin:$PATH"
export OMNI_KIT_ACCEPT_EULA=YES
export LD_PRELOAD="/lib/aarch64-linux-gnu/libgomp.so.1${LD_PRELOAD:+:$LD_PRELOAD}"

cd /home/robotics/isaac/IsaacLab

CMD=(uv run isaaclab play --rl_library rsl_rl --task "${TASK}" --num_envs "${NUM_ENVS}")

if [[ -n "${CHECKPOINT}" && "${CHECKPOINT}" != "latest" ]]; then
  CMD+=(--checkpoint "${CHECKPOINT}")
fi

echo "=========================================================="
echo " Playing Bittle Policy in Isaac Sim"
echo "  Task:         ${TASK}"
echo "  Environments: ${NUM_ENVS}"
echo "  Checkpoint:   ${CHECKPOINT:-latest}"
echo "=========================================================="

exec "${CMD[@]}" "${EXTRA_ARGS[@]}"
