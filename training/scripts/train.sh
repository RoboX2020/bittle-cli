#!/usr/bin/env bash
# ==============================================================================
# Petoi Bittle Quadruped RL Training Script for Isaac Sim / Isaac Lab
# Platform: NVIDIA GB10 | Isaac Sim 6.2 | Isaac Lab 3.0 | RSL-RL PPO
# ==============================================================================

set -e

# Default settings
TERRAIN="flat"        # Options: flat, rough
NUM_ENVS=2048         # Parallel environments on GPU
MAX_ITERS=1500        # Locomotion training iterations
RL_LIB="rsl_rl"       # RL backend
EXTRA_ARGS=()

# Parse options
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
    --max_iterations|-m)
      MAX_ITERS="$2"
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
    --checkpoint|-c)
      EXTRA_ARGS+=(--checkpoint "$2")
      shift 2
      ;;
    --help|-h)
      echo "Usage: ./train.sh [options] [-- <additional isaaclab flags>]"
      echo ""
      echo "Options:"
      echo "  -t, --terrain         Terrain type: 'flat' or 'rough' [default: flat]"
      echo "  -n, --num_envs        Number of parallel environments [default: 2048]"
      echo "  -m, --max_iterations  Maximum training iterations [default: 1500]"
      echo "  -c, --checkpoint      Resume training from checkpoint"
      echo "  --livestream [1|2]    Enable Omniverse WebRTC streaming (e.g. --livestream 1)"
      echo "  --viz kit             Enable interactive desktop GUI viewer"
      echo ""
      echo "Examples:"
      echo "  ./train.sh"
      echo "  ./train.sh --terrain rough --num_envs 4096"
      echo "  ./train.sh --viz kit --num_envs 16"
      echo "  ./train.sh --livestream 1"
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

echo "=========================================================="
echo " Starting Petoi Bittle RL Training (Isaac Sim / Isaac Lab)"
echo "  Robot:          Petoi Bittle (8-DoF Quadruped)"
echo "  Terrain:        ${TERRAIN_CAP}"
echo "  Task:           ${TASK}"
echo "  Environments:   ${NUM_ENVS}"
echo "  Max Iterations: ${MAX_ITERS}"
echo "  RL Library:     ${RL_LIB}"
echo "=========================================================="

export PATH="/home/robotics/.local/bin:$PATH"
export OMNI_KIT_ACCEPT_EULA=YES
export LD_PRELOAD="/lib/aarch64-linux-gnu/libgomp.so.1${LD_PRELOAD:+:$LD_PRELOAD}"

cd /home/robotics/isaac/IsaacLab

exec uv run isaaclab train \
  --rl_library "${RL_LIB}" \
  --task "${TASK}" \
  --num_envs "${NUM_ENVS}" \
  --max_iterations "${MAX_ITERS}" \
  "${EXTRA_ARGS[@]}"
