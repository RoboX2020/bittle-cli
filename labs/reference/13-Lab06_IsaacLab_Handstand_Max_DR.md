# Lab 06: 1:1 Real-Scale Bittle Handstand RL with Max Domain Randomization

## Learning Objectives
By the end of this lab, you will be able to:
1. Formulate a handstand RL task (`Isaac-Handstand-Bittle`) using body-frame gravity projection (`projected_gravity_b -> [0, +1, 0]`).
2. Prevent RL reward hacking (nose-propping, sky-jumping, and knee/elbow-on-ground cheating).
3. Debug and resolve PPO value-loss explosions (`3153.97`) and Newton MJWarp contact solver NaNs on lightweight robots.
4. Train an Option 2 **Asymmetric Actor-Critic** policy at **1:1 real robot scale** with 11 domain randomization mechanisms.

---

## 1. Handstand Reward Shaping & Preventing Exploits

In `bittle.usd`, `+Y` points toward the front shoulders. During a vertical handstand, world gravity `[0, 0, -1]` expressed in body frame (`projected_gravity_b`) equals **`[0, +1, 0]`**.

Key anti-exploit terms in [handstand_mdp.py](../../training/isaaclab_bittle_config/handstand_mdp.py):
1. **Prevent Nose-Propping:** Immediate termination on `base_frame_link` ground contact (`illegal_contact`).
2. **Prevent Sky-Jumping:** Early runs jumped to `z = 2.88 m` to farm absolute height rewards. Replaced absolute rear height with **`rear_above_base_reward`** (`z_rear - z_base`, completely invariant to jumping!) plus a bounded **`jump_height_penalty`**.
3. **Enforce "Knees Don't Touch Ground":**
   - **`front_knees_elevated_reward`** (`+4.0`): rewards keeping front knee joints elevated (`1.5–4.5 cm` in 1:1 scale).
   - **`front_knees_low_penalty`** (`-8.0`): penalizes dropping front knee joints below `3.0 cm` while inverted.
   - **`shoulder_contact_penalty`** (`-10.0`): penalizes any `.*_shoulder_link` contact so Bittle cannot rest on its elbows/forearms.
   - **`handstand_hold_bonus`** (`+10.0`): fires **only** when `g_y > 0.85`, torso height `7.5–14.5 cm`, both front paws on floor, no rear contact, no shoulder contact, and both front knees `> 3.0 cm` off the ground.

---

## 2. Debugging Physics Explosions & Value-Loss Blowups (What Didn't Work → Fixes)

During development on `2026-11-25`, we hit and solved three classic RL/physics failures:
1. **Unbounded Quadratic `jump_penalty` → Value Loss `3153.97` → `action_std = 4.18` → NaN (Iter 480–501):**
   - **Fix:** Bounded `jump_height_penalty` and `handstand_stability_penalty`, enabled `obs_normalization = True`, set `clip_actions = 4.0`, `std_range = (0.05, 1.5)`, `entropy_coef = 0.002`.
2. **Newton Contact Stiffness Mismatch (`ke = 160000` on `0.006 kg` Link → `inf` at Iter ~660):**
   - `RoughPhysicsCfg` defaulted to `ke = 160000, kd = 1100` (for 50 kg humanoids).
   - **Fix:** Lowered `ke = 2500, kd = 80` (for 1:1 `0.271 kg` Bittle) with `num_substeps = 4`, plus `--continuous` auto-resume in `train_handstand.sh`.
3. **10× Scale & Asymmetric Actor-Critic (`handstand_10x` → `handstand_real_1x`):**
   - Migrated from `usd_10x` to `usd_real_1x` (`0.1×` scale, `DelayedPDActuatorCfg` `20–40 ms` lag, `0.35 N·m`, `6.1 rad/s`), and switched the deployed Actor to **IMU + action history only** (`base_ang_vel`, `projected_gravity`, `actions` × 4 frames = `56` dims), while the simulation Critic retains privileged state (`66` dims).

---

## 3. Maximum Domain Randomization (11 Mechanisms)

Configured in [handstand_env_cfg.py](../../training/isaaclab_bittle_config/handstand_env_cfg.py):
1. Ground friction (`0.25–1.6` static, `0.2–1.4` dynamic) & restitution (`0.0–0.2`)
2. Torso mass scaling (`0.8–1.3×`, log-uniform)
3. All leg link mass scaling (`0.8–1.3×`, log-uniform)
4. Torso CoM perturbations (`x ±8 mm`, `y ±10 mm`, `z ±5 mm`)
5. Diagonal inertia scaling (`0.8–1.3×`)
6. Actuator stiffness (`0.65–1.45×`) & damping (`0.6–1.6×`) scaling
7. Joint friction (`0.0–0.015`) & armature (`0.0002–0.001`)
8. Per-world gravity vector perturbations (`±0.5, ±0.5, ±0.8 m/s²`)
9. Persistent per-episode disturbance wrench (`force ±0.12 N`, `torque ±0.01 N·m`)
10. Initial root pose/velocity & joint offset randomization (`±0.25 rad`)
11. Interval 6-axis velocity pushes every `3–6 s` + strong IMU noise (`base_ang_vel ±0.35`, `projected_gravity ±0.08`)

---

## 4. Verified Results & Archived Checkpoints

### Phase A: 10× Scale Policy ([model_4700.pt](../../training/models/handstand_10x/model_4700.pt), Iteration 4,700)
Evaluated across `64` environments for `10 s` (`500` steps):
- **Under Max Domain Randomization (with pushes & sensor noise):**
  - **`53 / 64` (83%)** held strict two-front-leg handstand for `>= 2 s` (mean hold `4.35 s`)
  - **`42 / 64` (66%)** survived all 10 seconds without torso/head contact; step `499`: `gy = 0.930`, `no_rear = 64/64`
- **Under Clean Physics:**
  - Step `499`: **`63 / 64` (98.4%)** both front legs planted, **`64 / 64` (100%)** rear legs airborne, mean `gy = 0.941`, **`42 / 64` (66%)** survived full 10 s.

### Phase B: 1:1 Real-Scale IMU-Only + Knees-Off-Ground ([handstand_real_1x](https://github.com/RoboX2020/bittle-cli/tree/main/training/models/handstand_real_1x))
Actively training (`train_handstand.sh --continuous --num_envs 2048 --max_iterations 1000000`):
```bash
cd /home/robotics/isaac/bittle_training
./train_handstand.sh --continuous --num_envs 2048 --max_iterations 1000000
./play_handstand.sh --viz kit --num_envs 4
```

---

## Verification Checklist
- [ ] Run `./play_handstand.sh --viz kit --num_envs 4` to visually verify handstand posture & knees off ground
- [ ] Check [training/logs/handstand_10x_summary.log](../../training/logs/handstand_10x_summary.log) and [training/logs/handstand_real_1x_summary.log](../../training/logs/handstand_real_1x_summary.log)
