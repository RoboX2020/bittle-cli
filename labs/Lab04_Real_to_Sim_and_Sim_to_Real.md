# Lab 04: Real-to-Sim System ID & Sim-to-Real Control Bridges

## Learning Objectives
By the end of this lab, you will be able to:
1. Map Isaac Lab's 8-DoF joint ordering to OpenCat's 16-channel servo indices.
2. Quantify physical two-leg balance limits and wireless link latency using `sim/stand_sim.py`.
3. Understand the custom `OpenCatEsp32` closed-loop firmware patch (`firmware/balanceStand.h` + `balance_stand.patch`).
4. Choose between Open-Loop `K`-token distillation and Closed-Loop IMU-only Option 2 deployment.

---

## 1. Joint & Coordinate Mapping (Isaac Sim ↔ OpenCatEsp32)

| OpenCat Index | Physical Servo | Isaac Lab Joint Name |
|---|---|---|
| `8` | Front Left Shoulder | `left_front_shoulder_joint` |
| `9` | Front Right Shoulder | `right_front_shoulder_joint` |
| `10` | Back Right Hip | `right_back_shoulder_joint` |
| `11` | Back Left Hip | `left_back_shoulder_joint` |
| `12` | Front Left Knee | `left_front_knee_joint` |
| `13` | Front Right Knee | `right_front_knee_joint` |
| `14` | Back Right Knee | `right_back_knee_joint` |
| `15` | Back Left Knee | `left_back_knee_joint` |

> **Remember:** In `bittle.usd`, `right_*_knee_joint` has a `180°` `localRot0` flip relative to `left_*_knee_joint`. Always verify joint sign conventions on a foam mat before sending live RL joint targets to hardware!

---

## 2. Planar Physics & Link-Latency Analysis (`sim/stand_sim.py`)

Run the planar two-leg stand physics simulator:
```bash
python3 sim/stand_sim.py --links
```

Observed results (`MB=0.25 kg`, `MA=0.04 kg`, `L1=0.085 m`, `L2=0.07 m`, `TAU=0.035 s`, `WMAX=350°/s`):

| Paw Contact Length | Static Pose Window | Hold Pose (No PID) | PID on Body Pitch | PID on Leg Tilt |
|---|---|---|---|---|
| `4 mm` (toe tips) | `±1°` | `1.2 mN s` | `0.0 mN s` (falls) | `0.0 mN s` (falls) |
| `8 mm` | `±3°` | `5.9 mN s` | `0.0 mN s` (falls) | `0.0 mN s` (falls) |
| `16 mm` | `±6°` | `15.2 mN s` | `0.0 mN s` (falls) | `0.0 mN s` (falls) |
| `30 mm` | `±12°` | `31.6 mN s` | `0.0 mN s` (falls) | `0.0 mN s` (falls) |
| `50 mm` (shin/pads) | `±21°` | `55.1 mN s` | `41.0 mN s` | `0.0 mN s` (falls) |

**Control Link Tolerance (`50 mm` contact, PID on pitch):**
- Onboard firmware PID (`12 ms` delay / `5 ms` tick): **`41.0 mN s`**
- Laptop over USB serial (`30 ms` / `10 ms`): **`34.0 mN s`**
- Laptop over BLE (`75 ms` / `15 ms`): **`17.6 mN s`**
- Laptop over WiFi (`90 ms` / `20 ms`): **`0.0 mN s` (fails)**

**Physical Conclusion:** Bittle has no ankle actuators. Over BLE (`75 ms` lag) or open-loop animation, `4 mm` toe-tip handstands tip within a `±1°` window (which is why our real hardware test of `bittle --ble play handstand` hit its head and self-righted). Real two-leg balance requires either high-rate onboard/USB closed-loop control (`>= 50–200 Hz`) or a wider contact patch.

---

## 3. Custom Closed-Loop Firmware Patch (`firmware/`)

`firmware/balanceStand.h` and `firmware/balance_stand.patch` add serial token `'y'` (`yh`, `yr`, `yg`, `yx`, `yz`, `ya`, `yp`, `ys`, `ym`, `yc`, `yl`, `yf`, `yw`, `yb`, `yB`, `yt`, `ye`, `yu`, `y?`) to `OpenCatEsp32` (pinned at commit `84dd6eff307eb2f4af6f9cbdf72f04e7d71beecf`), providing:
- `~200 Hz` onboard IMU loop (`balanceLoop()`)
- Automatic four-leg fall catch (`standCatch()`)
- `~50–100 Hz` `#B ms pitch err u roll` telemetry (`stand watch` / `stand laptop`)

**Current Status:** Host-tested under `BALANCE_STAND_HOST_TEST`; **not yet compiled for ESP32 or flashed onto hardware**. See [HANDSTAND_AND_FIRMWARE.md](../docs/HANDSTAND_AND_FIRMWARE.md) for flashing steps.

---

## 4. Real-to-Sim & Sim-to-Real Deployment Paths

### Real-to-Sim System Identification
Match simulation actuators to physical P1S micro-servos using `DelayedPDActuatorCfg`:
- `effort_limit = 0.35 N·m`, `velocity_limit = 6.1 rad/s` (`350°/s`)
- `min_delay = 4`, `max_delay = 8` steps (`20–40 ms` lag at `dt = 0.005 s`)
- Domain randomization over mass, CoM, inertia, joint friction, stiffness/damping, and floor friction.

### Sim-to-Real Deployment Options
1. **Option 1 — Open-Loop `K` Trajectory Export (BLE-compatible):** Sample simulation joint trajectories at `20 Hz` (`50 ms`), convert radians to OpenCat `int8` degrees, and upload via `K`.
2. **Option 2 — Closed-Loop IMU-Only Policy (USB Serial / Onboard ESP32):** Train with an **Asymmetric Actor-Critic** where the deployed Actor sees **only** `[base_ang_vel, projected_gravity, last_action]` stacked over `history_length = 4` (`56` dims) — eliminating unobservable `base_lin_vel` and servo encoders (implemented in **Lab 06**).

---

## Verification Checklist
- [ ] Run `python3 sim/stand_sim.py --links` and verify link-latency output
- [ ] Verify `patch --dry-run -p1 < firmware/balance_stand.patch` against `OpenCatEsp32` (`84dd6eff`) before flashing
