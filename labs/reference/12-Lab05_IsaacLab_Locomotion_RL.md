# Lab 05: Quadruped Locomotion RL in Isaac Lab 3.0 (Flat & Rough)

## Learning Objectives
By the end of this lab, you will be able to:
1. Register custom Petoi Bittle tasks (`Isaac-Velocity-Flat-Bittle`, `Isaac-Velocity-Rough-Bittle`) in Isaac Lab 3.0 with Newton MJWarp.
2. Configure ARM64 (`aarch64` NVIDIA GB10) runtime environment variables (`LD_PRELOAD=libgomp.so.1`).
3. Train, monitor via TensorBoard, and evaluate converged locomotion policies (`training/models/locomotion_flat/`).

---

## 1. Environment & Task Registration

Task source files archived in [training/isaaclab_bittle_config/](https://github.com/RoboX2020/bittle-cli/tree/main/training/isaaclab_bittle_config):
- `__init__.py` — Registers `Isaac-Velocity-Flat-Bittle` and `Isaac-Velocity-Rough-Bittle`
- `flat_env_cfg.py` & `rough_env_cfg.py` — Uses `assets/usd_10x/bittle.usd` (`_BITTLE_STANDING_HEIGHT = 0.58`, `pos = (0, 0, 0.62)`, `stiffness = 25.0`, `damping = 1.0`, `effort_limit = 15.0`, `action scale = 0.25`)
- `agents/rsl_rl_ppo_cfg.py` — `BittleFlatPPORunnerCfg` (`[128, 128, 64]` ELU MLPs, `lr = 1e-3`, adaptive KL `0.01`, `gamma = 0.99`, `lam = 0.95`)

### Critical ARM64 Runtime Requirements (`training/scripts/train.sh`)
On Ubuntu `aarch64` (NVIDIA GB10), launching Isaac Lab requires:
```bash
export OMNI_KIT_ACCEPT_EULA=YES
export LD_PRELOAD="/lib/aarch64-linux-gnu/libgomp.so.1${LD_PRELOAD:+:$LD_PRELOAD}"
```

---

## 2. Training & Playback Commands

```bash
cd /home/robotics/isaac/bittle_training   # scripts archived in training/scripts/

# 1. Train flat-terrain velocity tracking (2,048 parallel envs, 1,500 iters)
./train.sh --terrain flat --num_envs 2048 --max_iterations 1500

# 2. Evaluate converged policy in Isaac Sim desktop GUI
./play.sh --checkpoint bittle_policy_final.pt --viz kit --num_envs 4

# 3. Stream over WebRTC (http://localhost:8211/streaming/webrtc-demo/)
./play.sh --checkpoint bittle_policy_final.pt --livestream 1 --num_envs 8

# 4. Monitor TensorBoard (http://localhost:6006)
./start_tensorboard.sh
```

---

## 3. Experimental Results (Included in `training/models/locomotion_flat/` & `training/logs/`)

Three runs were executed on `2026-11-14`:
1. **5-iter smoke test (`10-55-20`):** `Mean reward: -5.03`, `Mean ep len: 60.00`, `base_contact: 0.1413`
2. **10-iter smoke test (`10-56-31`):** `Mean reward: -7.08`, `Mean ep len: 106.39`, `base_contact: 0.2780`
3. **1,500-iter full run (`10-57-04`):** `2,048` envs, **`73,728,000` steps** in **`1,648.86 s`** (~`44,739 steps/s`):
   - **`Mean reward: 29.46`**
   - **`Mean episode length: 1000.00` / `1000.00`**
   - **`Metrics/success_rate: 1.0000` (100%)**
   - **`Episode_Termination/base_contact: 0.0000` (0 falls)**
   - `error_vel_xy: 0.2285`, `error_vel_yaw: 0.2583`, `feet_air_time: -0.0105`

Archived artifacts in [training/models/locomotion_flat/](https://github.com/RoboX2020/bittle-cli/tree/main/training/models/locomotion_flat):
- `bittle_policy_final.pt` (`735,925` bytes, SHA-256 `db95a6fdabaabcf22089a42e11c83b8f8178c38955d6f21970c82372270a8d5c`)
- `exported/policy.pt` (`133,334` bytes TorchScript policy)
- `params/{agent,env}.yaml`, `run.json`, and TensorBoard `events.out.tfevents.*`

**Not Yet Done:** `Isaac-Velocity-Rough-Bittle` was registered (`rough_env_cfg.py`) but not yet trained.

---

## Verification Checklist
- [ ] Inspect [training/logs/locomotion_flat_summary.log](../../training/logs/locomotion_flat_summary.log)
- [ ] Play `training/models/locomotion_flat/bittle_policy_final.pt` with `play.sh --viz kit`
