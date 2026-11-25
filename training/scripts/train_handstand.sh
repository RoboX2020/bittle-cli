#!/usr/bin/env bash
# ==============================================================================
# Petoi Bittle Handstand RL Training Script (Max Domain Randomization)
# Platform: NVIDIA GB10 | Isaac Sim 6.2 | Isaac Lab 3.0 | RSL-RL PPO
# ==============================================================================

set -e

NUM_ENVS=2048
MAX_ITERS=50000
RL_LIB="rsl_rl"
TASK="Isaac-Handstand-Bittle"
CONTINUOUS=0
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
  case $1 in
    --num_envs|-n)
      NUM_ENVS="$2"
      shift 2
      ;;
    --max_iterations|-m)
      MAX_ITERS="$2"
      shift 2
      ;;
    --continuous)
      CONTINUOUS=1
      shift
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
    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

echo "=========================================================="
echo " Starting Petoi Bittle HANDSTAND RL Training"
echo "  Task:           ${TASK}"
echo "  Environments:   ${NUM_ENVS}"
echo "  Max Iterations: ${MAX_ITERS}"
echo "  Continuous:     ${CONTINUOUS}"
echo "  Domain Rand:    MAX (friction, mass, CoM, inertia, gains, joints, gravity, pushes, noise)"
echo "=========================================================="

export PATH="/home/robotics/.local/bin:$PATH"
export OMNI_KIT_ACCEPT_EULA=YES
export LD_PRELOAD="/lib/aarch64-linux-gnu/libgomp.so.1${LD_PRELOAD:+:$LD_PRELOAD}"

cd /home/robotics/isaac/IsaacLab

if [[ "${CONTINUOUS}" -eq 1 ]]; then
  while true; do
    set +e
    uv run isaaclab train \
      --rl_library "${RL_LIB}" \
      --task "${TASK}" \
      --num_envs "${NUM_ENVS}" \
      --max_iterations "${MAX_ITERS}" \
      "${EXTRA_ARGS[@]}"
    STATUS=$?
    set -e
    if [[ ${STATUS} -eq 0 ]]; then
      echo "[train_handstand] Completed cleanly."
      break
    fi
    echo "[train_handstand] Exited with code ${STATUS}; auto-resuming from latest checkpoint in 3s..."
    # Replace/set --checkpoint latest for subsequent resumes
    NEW_ARGS=()
    SKIP_NEXT=0
    for arg in "${EXTRA_ARGS[@]}"; do
      if [[ ${SKIP_NEXT} -eq 1 ]]; then
        SKIP_NEXT=0
        continue
      fi
      if [[ "${arg}" == "--checkpoint" || "${arg}" == "-c" ]]; then
        SKIP_NEXT=1
        continue
      fi
      NEW_ARGS+=("${arg}")
    done
    EXTRA_ARGS=("${NEW_ARGS[@]}" --checkpoint latest)
    sleep 3
  done
else
  exec uv run isaaclab train \
    --rl_library "${RL_LIB}" \
    --task "${TASK}" \
    --num_envs "${NUM_ENVS}" \
    --max_iterations "${MAX_ITERS}" \
    "${EXTRA_ARGS[@]}"
fi
