# Isaac Sim, Isaac Lab RL Training & Sim-to-Real Architecture

This document records all NVIDIA Isaac Sim / Isaac Lab reinforcement learning work for Petoi Bittle present on this workstation (`spark-a318`, NVIDIA GB10 GPU, `aarch64` Ubuntu 24.04).

---

## 1. Two Isaac Workspaces on Disk

### A. Legacy Isaac Sim 4.5.0 Repo (`/home/robotics/isaac/Bittle-IsaacSim`)
- Cloned from `https://github.com/Dafodilrat/Bittle-IsaacSim.git` (latest commit `51b3260 decrease ground size`).
- Contains original `Bittle_URDF/bittle/` USD conversion, Docker files, `launch.py`, and PyQt5/extension trainer (`exts/customView/customView/`).
- **Status:** The `RL Viewport` Isaac Sim extension (`ext.py`) is **broken/deprecated** due to Isaac Sim API changes. Superseded by the Isaac Lab 3.0 workspace below.

### B. Active Isaac Lab 3.0 / Isaac Sim 6.2 RL Workspace (`/home/robotics/isaac/bittle_training` & `/home/robotics/isaac/IsaacLab`)
- **USD Asset Fix (`/home/robotics/isaac/bittle_asset/`):**
  - The original `Bittle_URDF/bittle/bittle.usd` and `configuration/bittle_physics.usd` had `ArticulationRootAPI` applied to **both** `/bittle` and `/bittle/base_frame_link`, causing Isaac Lab spawning to fail.
  - Copied to `/home/robotics/isaac/bittle_asset/` and stripped the duplicate `ArticulationRootAPI` from `/bittle/base_frame_link`, leaving `/bittle` as the single articulation root.
- **Registered Isaac Lab Tasks (`IsaacLab/source/isaaclab_tasks/isaaclab_tasks/core/velocity/config/bittle/`):**
  - `Isaac-Velocity-Flat-Bittle` (`BittleFlatEnvCfg` + `BittleFlatPPORunnerCfg`)
  - `Isaac-Velocity-Rough-Bittle` (`BittleRoughEnvCfg` + `BittleRoughPPORunnerCfg`) — configured, **not yet trained**
- **Robot Configuration (`rough_env_cfg.py` & `bittle_env_cfg.py`):**
  - **8-DoF Quadruped:** `.*_shoulder_joint` (init `0.0`), `.*_knee_joint` (init `0.2`), initial spawn `z = 0.62`, target base height `_BITTLE_STANDING_HEIGHT = 0.58`.
  - **Actuators (`ImplicitActuatorCfg`):** `effort_limit=15.0`, `velocity_limit=10.0`, `stiffness=25.0`, `damping=1.0`, action scale `0.25`.
  - **Observations / Actions:** 36-dim policy observation, 8-dim normalized joint target angles.
  - **Flat PPO Network (`BittleFlatPPORunnerCfg`):** Actor & Critic MLPs `[128, 128, 64]`, `elu`, `learning_rate=1e-3` (adaptive KL `0.01`), `gamma=0.99`, `lam=0.95`, `entropy_coef=0.01`, `num_steps_per_env=24`, `seed=42`.
  - **ARM64 (`aarch64`) Runtime Requirement:** Must export `LD_PRELOAD=/lib/aarch64-linux-gnu/libgomp.so.1` and `OMNI_KIT_ACCEPT_EULA=YES` (handled automatically in `train.sh` and `play.sh`).

---

## 2. Training Runs & Verified Results

Three training runs exist in `/home/robotics/isaac/IsaacLab/logs/rsl_rl/bittle_flat/`:

| Run Directory | Iterations | Num Envs | Result |
|---|---|---|---|
| `2026-11-14_10-55-20` | `5` (smoke test) | `64` | `Mean reward: -5.03`, `Mean ep len: 60.00`, `base_contact: 0.1413`, `success_rate: 0.0` |
| `2026-11-14_10-56-31` | `10` (smoke test) | `64` | `Mean reward: -7.08`, `Mean ep len: 106.39`, `base_contact: 0.2780`, `success_rate: 0.0` |
| `2026-11-14_10-57-04` | **`1500`** (full run) | **`2048`** | **Converged:** `73,728,000` steps in `1648.86 s` (~44,739 steps/s). `Mean reward: 29.46`, `Mean ep len: 1000.00`, `Metrics/success_rate: 1.0000`, `base_contact: 0.0000` (0 falls), `error_vel_xy: 0.2285`, `error_vel_yaw: 0.2583`, `feet_air_time: -0.0105`. |

### Exported Policy Artifacts
- `/home/robotics/isaac/bittle_training/bittle_policy_final.pt` (`735,925` bytes, SHA-256 `db95a6fdabaabcf22089a42e11c83b8f8178c38955d6f21970c82372270a8d5c` — identical to `model_1499.pt`)
- `/home/robotics/isaac/IsaacLab/logs/rsl_rl/bittle_flat/2026-11-14_10-57-04/exported/policy.pt` (`133,334` bytes TorchScript policy, SHA-256 `3867d43f1db2c87c997af4373f1affc9623b6abd01a33f52c67c1829deb80e47`)

### Commands to Replay or Train
```bash
cd /home/robotics/isaac/bittle_training

# Play converged policy in Isaac Sim desktop GUI
./play.sh --checkpoint bittle_policy_final.pt --viz kit --num_envs 4

# Stream over WebRTC (open http://localhost:8211/streaming/webrtc-demo/)
./play.sh --checkpoint bittle_policy_final.pt --livestream 1 --num_envs 8

# Launch TensorBoard (open http://localhost:6006)
./start_tensorboard.sh
```

---

## 3. Sim-to-Real & Real-to-Sim Architecture (Designed, Not Yet Implemented)

> **Status:** Conceptual architecture and joint mapping have been designed, **but no Python bridge script has been written or run against the real Bittle yet**.

### Planned Transport Paths
1. **Trajectory / Combo Export (`K` token) — Open-Loop:** Sample simulated rollouts at 20 Hz (50 ms) and pack into `[-frames, 0, 0, ratio, ...]` for onboard ESP32 execution without radio jitter.
2. **Real-Time Joint Streaming (`o` / `I` tokens) — Closed-Loop RL:** Stream 8-DoF joint targets from `policy.pt` over USB serial (`115200` baud) or WiFi WebSocket, reading IMU pitch/roll telemetry for Real-to-Sim system identification.
3. **Domain Randomization Needed for PWM Servos:** Actuator PD tuning, 20–50 ms action latency injection, base mass randomization (±10–15%), and foot ground friction (`0.4–1.0`).

### Joint Mapping Reference (OpenCat 16-Channel ↔ Isaac Sim 8-DoF)

| OpenCat Joint Index | Bittle Joint | Isaac Sim Joint |
|---|---|---|
| `8` | Front Left Shoulder | `FL_shoulder_joint` / `FL_hip_joint` |
| `9` | Front Right Shoulder | `FR_shoulder_joint` / `FR_hip_joint` |
| `10` | Back Right Hip | `RR_shoulder_joint` / `RR_hip_joint` |
| `11` | Back Left Hip | `RL_shoulder_joint` / `RL_hip_joint` |
| `12` | Front Left Knee | `FL_knee_joint` |
| `13` | Front Right Knee | `FR_knee_joint` |
| `14` | Back Right Knee | `RR_knee_joint` |
| `15` | Back Left Knee | `RL_knee_joint` |
| `0` / `1` | Head Pan / Tilt | Optional (unused in 8-DoF RL) |
