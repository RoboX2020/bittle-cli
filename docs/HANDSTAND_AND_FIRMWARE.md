# Handstand, Rear Stand & Firmware Patch (`balanceStand.h`)

The factory OpenCatEsp32 firmware cannot hold a two-leg stand:
1. Built-in gyro balancing (`gB`) is tuned for four-legged posture and triggers self-righting (`rc`) when pitched vertically.
2. Standard telemetry is far too slow (~5 Hz) for laptop-side balancing.
3. On the tested Bittle X (`PetoiBLE-4CB5`), stock `khds` and `khu` were not even compiled into flash ROM (returning `?\r\n k`).

This repo includes a planar physics simulator (`sim/stand_sim.py`), CLI support (`stand ...` in `bittle_cli.py`), and a custom C++ firmware module (`firmware/balanceStand.h` + `firmware/balance_stand.patch`).

> **Current Status:** `sim/stand_sim.py` has been run and verified. `firmware/balanceStand.h` compiles with host stand-ins (`BALANCE_STAND_HOST_TEST`), **but has NOT been compiled for ESP32 or flashed onto the robot**.

---

## 1. Physics Simulation Results (`sim/stand_sim.py`)

Running `python3 sim/stand_sim.py --links` evaluates a planar rigid-body model of Bittle (`MB=0.25 kg`, `MA=0.04 kg`, `L1=0.085 m`, `L2=0.07 m`, `LB=0.11 m`, `LA=0.07 m`, servo lag `TAU=0.035 s`, speed limit `350 deg/s`, IMU noise `0.3°`):

| Paw Contact Length | Pose Window | No Control (Hold Pose) | PID on Body Pitch (`kp=1, kd=0.05, sign=-1`) | PID on Leg Tilt (`kp=2, kd=0.1, mix=1`) |
|---|---|---|---|---|
| `4 mm` (toe tips) | `±1°` | `1.2 mN s` | `0.0 mN s` (falls) | `0.0 mN s` (falls) |
| `8 mm` | `±3°` | `5.9 mN s` | `0.0 mN s` (falls) | `0.0 mN s` (falls) |
| `16 mm` | `±6°` | `15.2 mN s` | `0.0 mN s` (falls) | `0.0 mN s` (falls) |
| `30 mm` | `±12°` | `31.6 mN s` | `0.0 mN s` (falls) | `0.0 mN s` (falls) |
| `50 mm` (shins / pads) | `±21°` | `55.1 mN s` | `41.0 mN s` | `0.0 mN s` (falls) |

**Control Link Latency Comparison (50 mm contact, PID on body pitch):**

| Control Link | Assumed Delay / Period | Shove Survived |
|---|---|---|
| Onboard (firmware PID) | `12 ms` / `5 ms` | `41.0 mN s` |
| Laptop over USB serial | `30 ms` / `10 ms` | `34.0 mN s` |
| Laptop over BLE | `75 ms` / `15 ms` | `17.6 mN s` |
| Laptop over WiFi | `90 ms` / `20 ms` | `0.0 mN s` (fails) |

### Key Mechanical Takeaways
- Bittle has **no ankle actuators**. Once the center of mass moves past the paw edge, the paw acts as a free pivot; driving a shoulder mostly swings the lightweight airborne legs rather than torquing the body back over the paw.
- Because `4 mm` paw tips give only a `±1°` static pose window, **an accurate balanced top pose + wider contact patch (e.g. resting on lower legs/shins) + fall-catch reflex** matters far more than fast PID gains. That is why `balanceStand.h` defaults all PID gains (`kp`, `ki`, `kd`) to `0`.

---

## 2. Firmware Patch Files & Installation

| File | Description |
|---|---|
| `firmware/balanceStand.h` | Implements `StandPID`, `handstandEntry`, `rearEntry`, `fourLegPose` fall catch, `balanceLoop()` (~200 Hz IMU tick), and `standCommand()` on serial token `'y'`. |
| `firmware/balance_stand.patch` | Patches `OpenCatEsp32.ino`, `src/OpenCat.h`, adds `src/balanceStand.h`, and hooks `'y'` into `src/reaction.h`. |

### Flashing Steps (Not Yet Executed on Hardware)
1. Clone `OpenCatEsp32` at the pinned commit `84dd6eff307eb2f4af6f9cbdf72f04e7d71beecf` (newer commits may apply with offsets):
   ```bash
   git clone https://github.com/PetoiCamp/OpenCatEsp32.git
   cd OpenCatEsp32
   git checkout 84dd6eff307eb2f4af6f9cbdf72f04e7d71beecf
   ```
2. Apply the patch:
   ```bash
   patch -p1 < /home/robotics/bittle-cli/firmware/balance_stand.patch
   ```
3. Build and upload `OpenCatEsp32.ino` to the BiBoard over USB using Arduino IDE.
4. Verify in `bittle-cli`:
   ```bash
   bittle --serial /dev/ttyUSB0 y?
   ```
   Expected reply starts with `#P mode ...` and `#Q ...`.

---

## 3. CLI `stand` Commands & Raw `'y'` Protocol

| CLI Command | Raw Token | Action |
|---|---|---|
| `stand hand` | `yh` | Climb `handstandEntry` keyframes, then enter stand hold/balance mode |
| `stand rear` | `yr` | Climb `rearEntry` keyframes, then enter rear-stand hold/balance mode |
| `stand here` | `yg` | Hold/balance from current joint angles |
| `stand stop` | `yx` | Stop stand mode and hold pose (any non-`y` command also exits) |
| `stand zero` | `yz` | Capture current `ypr[1]` pitch as setpoint |
| `stand pose IDX DEG` | `yb IDX DEG` | Trim joint `IDX` (`0..15`) of the base pose (remembered until reboot) |
| `stand gains KP KI KD` | `yp KP KI KD` | Set onboard PID gains (deg shoulder per deg pitch error) |
| `stand sign +1\|-1` | `ys +1\|-1` | Flip PID correction sign |
| `stand mix M` | `ym M` | `0` = body pitch error; `±1` = support-leg tilt (`pitch - setpoint - mix * u`) |
| `stand limit LIM FALL` | `yl LIM FALL` | Clamp `|u|` to `LIM` deg (default `30`) and trigger fall catch above `FALL` deg (default `35`) |
| `stand catch 0\|1` | `yc 0\|1` | Enable/disable automatic `fourLegPose` fall catch after `> 60 ms` beyond `fallLimit` |
| `stand show` | `y?` | Print `#P` parameters and `#Q` 16-DOF base pose |
| `stand watch SECS [CSV]` | `yt 4` | Live ~50 Hz ASCII tilt gauge (`#B ms pitch err u roll`), optional CSV export (USB/BLE only) |
| `stand laptop KP KI KD SECS` | `ye 1`, `yt 2`, `yu U` | ~100 Hz telemetry + laptop-computed correction `yu` (USB/BLE only; WiFi unsupported) |

Additional raw `'y'` subcommands in `balanceStand.h`:
- `ya DEG` — explicit pitch setpoint
- `yf ALPHA` — derivative low-pass filter (`0.01..1.0`, default `0.35`)
- `yw AIR KNEE ROLL` — airborne leg counterweight gain, support-knee bend gain, differential roll gain
- `yB` — snapshot `currentAng[0..15]` into `stand.base`

### Joint Index Reference
- `0`: Head pan/tilt
- `8` / `9`: Front left / front right shoulders
- `10` / `11`: Back right / back left hips (shoulders)
- `12` / `13`: Front left / front right knees
- `14` / `15`: Back right / back left knees

---

## 4. Open-Loop Fallback Combos (`combos.json`)

For unpatched stock firmware, `handstand` and `rearStand` were added to `combos.json` as 7-frame `K` binary arrays:
- `handstand`: `stand -> tuck -> leanF -> kick -> holdHDS@30 -> recover -> stand`
- `rearStand`: `stand -> sitBack -> tiltRear -> raiseFront -> holdRear@30 -> recover -> stand`

Because these are open-loop animations with `4 mm` toe contact (and `Joint 0 = +85°` in the handstand entry), **physical testing showed Bittle slams its head on the floor and falls instead of holding balance**. Always test on a soft surface with a hand ready to catch.
