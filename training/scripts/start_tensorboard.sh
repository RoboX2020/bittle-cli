#!/usr/bin/env bash
# ==============================================================================
# Launch TensorBoard for Bittle RL Training Logs
# ==============================================================================

LOGDIR="/home/robotics/isaac/IsaacLab/logs/rsl_rl"
PORT="${1:-6006}"

echo "=========================================================="
echo " Starting TensorBoard for Bittle RL Telemetry"
echo "  Log directory: ${LOGDIR}"
echo "  Web UI:        http://localhost:${PORT}"
echo "=========================================================="

cd /home/robotics/isaac/IsaacLab
exec uv run tensorboard --logdir "${LOGDIR}" --port "${PORT}" --bind_all
