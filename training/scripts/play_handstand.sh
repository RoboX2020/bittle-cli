#!/usr/bin/env bash
# ==============================================================================
# Petoi Bittle Handstand Policy Playback & Visualization Script
# ==============================================================================

set -e

NUM_ENVS=16
CHECKPOINT=""
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
  case $1 in
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
    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

export PATH="/home/robotics/.local/bin:$PATH"
export OMNI_KIT_ACCEPT_EULA=YES
export LD_PRELOAD="/lib/aarch64-linux-gnu/libgomp.so.1${LD_PRELOAD:+:$LD_PRELOAD}"

cd /home/robotics/isaac/IsaacLab

CMD=(uv run isaaclab play --rl_library rsl_rl --task "Isaac-Handstand-Bittle" --num_envs "${NUM_ENVS}")

if [[ -n "${CHECKPOINT}" && "${CHECKPOINT}" != "latest" ]]; then
  CMD+=(--checkpoint "${CHECKPOINT}")
fi

exec "${CMD[@]}" "${EXTRA_ARGS[@]}"
