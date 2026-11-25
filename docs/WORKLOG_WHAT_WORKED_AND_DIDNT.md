# Worklog: What Worked, What Didn't & Root Causes

This document records every technical experiment, bug fix, hardware test, simulation result, and failure mode encountered across all Bittle work on this workstation (`spark-a318`).

---

## 1. CLI Setup, Mock Simulator & Test Suite — **WORKED**

- **Packages installed & verified:** `pyserial` (`3.5`), `bleak` (`3.1.0`), `websockets` (`17.4` on system Python 3.12; `14.2` in `IsaacLab/.venv`).
- **Editable package install:** Installed `/home/robotics/bittle-cli` via `pip install -e .`, exposing `~/.local/bin/bittle` (`bittle_cli:main_cli`) and `~/.local/bin/bittle-mock` (`mock_bittle:main`).
- **Automated suite (`test_bittle.py`):** **10/10 tests pass** consistently:
  1. `bittle_cli.py list` (offline)
  2. `bittle_cli.py scan` (offline BlueZ + advertisement + serial port scan)
  3. WebSocket (`ws://127.0.0.1:8089`): `ksit`, `play flipShow` (`K` binary base64 + `gb`/`gB`), `chain moonwalkBow`, `chain partyTrick --onboard` (`q` token), `stop` (`d` token)
  4. Virtual Serial PTY (`/tmp/ttyBittle_test`): `ksit`, `play boxerCombo` (`K` binary + `~` terminator), `chain moonwalkBow`

### Packaging / Portability Fixes Applied in `bittle-cli`
When moving from `/home/robotics/Downloads/bittle` to the packaged `/home/robotics/bittle-cli` repo:
- Added `get_user_file()` fallback so `my_combos.json` falls back to `~/.config/bittle/my_combos.json` if the package install path is not writable.
- Hardened `Library.__init__` lookup for `combos.json` across explicit `--combos`, current working directory, and `HERE / "combos.json"`.
- Added `main_cli()` entrypoint wrapper in `bittle_cli.py` for `pyproject.toml` / `setup.py`.

---

## 2. Real Hardware Bluetooth LE (`PetoiBLE-4CB5`) — **FAILED INITIALLY, THEN FIXED & WORKED**

**Target hardware tested:** Petoi Bittle X (`PetoiBLE-4CB5`, MAC `60:33:66:0A:4C:B5`, public address).

### Why It Initially Failed
1. **GATT UUID Mismatch:**
   - The original `bittle_cli.py` hardcoded Nordic UART Service (`6e400001-b5a3-f393-e0a9-e50e24dcca9e`, RX `6e400002`, TX `6e400003`).
   - This Bittle X uses the TI/Petoi UART GATT service **`0000ffe0-0000-1000-8000-00805f9b34fb`** with shared characteristic **`0000ffe1-0000-1000-8000-00805f9b34fb`**.
2. **Paired / System-Connected Device Invisible to Advertisements:**
   - When the robot was paired or connected via Ubuntu's system Bluetooth settings, it stopped broadcasting BLE advertisement beacons.
   - `BleakScanner.discover()` returned nothing, causing `bittle --ble` to fail.
3. **BLE Connect Triggers ESP32 Boot / Stale `TimeoutError`:**
   - Connecting to `PetoiBLE-4CB5` resets/boots the BiBoard (`Init IMU` → `Init servos: 25.37MHz` → `Load skills` → `* Start *` → `Bittle` → `Ready!`).
   - Commands sent immediately during the first ~1–4 seconds were silently dropped by the firmware.
   - Also, when BlueZ held a stale paired/connected state or the robot wasn't ready, `BleakClient.connect()` occasionally hit `asyncio.TimeoutError` in `bleak/backends/bluezdbus/client.py`.
4. **2 ms Chunk Pacing Dropped Bytes on Binary `K` Uploads:**
   - The original `bittle_cli.py` (and `bittle_cli handstand.py`) used `await asyncio.sleep(0.002)` (2 ms) between 20-byte `CHUNK` writes.
   - Uploading the 149-byte `handstand` `K` payload at 2 ms pacing caused `(no confirmation for 'K' - it may still have run)` because the ESP32 BLE UART buffer dropped bytes.
5. **CLI Argument Ambiguity:**
   - Running `bittle --ble ksit` or `bittle --ble play flipShow` previously treated `ksit` / `play` as the `--ble NAME_OR_ADDR` device filter instead of the command.

### Fixes Implemented in `bittle_cli.py` (Verified on Hardware)
- **Dynamic GATT Discovery (`BleLink.open`):** Scans characteristics for `ffe1` (sets both `rx_char` and `tx_char`), `6e400002`/`6e400003` (Nordic NUS), and falls back to generic `write`/`write-without-response` + `notify` properties.
- **BlueZ Property Lookup (`find_ble` & `scan`):** Queries `get_global_bluez_manager()._properties` for `org.bluez.Device1` entries (`Connected` or `Paired`), filtering out classic-SPP-only (`1101`) devices unless they also carry BLE UART UUIDs, before falling back to `BleakScanner.discover()`.
- **Boot Banner Synchronization:** Listens for `"Ready!"` or `"Start"` (up to `4.5s` timeout) plus `0.5s` extra settle and clears stale boot lines from `self.lines`.
- **15 ms BLE Write Pacing:** Changed `Transport.send` inter-chunk delay from `0.002s` to `0.015s`.
- **Command Disambiguation:** Recognizes known CLI subcommands (`play`, `chain`, `mix`, `seq`, `gyro`, `stop`, `list`, `scan`, `help`, `stand`) and single-letter OpenCat command prefixes (`k`, `m`, `d`, `g`, `b`, `q`, `o`) passed directly after `--ble`.

### Hardware Verification Observed
- `bittle --ble ksit` and `bittle --ble kbalance` confirmed working (`robot> k`).
- Direct BLE probe of `handstand` (`149` bytes, `K` token, `20 ms` interval in standalone test and `15 ms` in `bittle_cli.py`) produced:
  ```text
  connecting to PetoiBLE-4CB5 (60:33:66:0A:4C:B5) ...
    robot> Init IMU
    robot> Init servos: 25.37MHz
    robot> Load skills
  > handstand: stand -> tuck -> leanF -> kick -> holdHDS@30 -> recover -> stand  (7 frames)
    gyro balancing off for this move (stops auto-recover from cutting it short)
    robot> * Start *
    robot> Bittle
    robot> Ready!
    robot> p
    robot> g
    robot> k
    robot> G
  ```

---

## 3. Handstand & Rear Stand Experiments — **STOCK SKILLS MISSING; OPEN-LOOP FAILED TO BALANCE**

### What Didn't Work
1. **Stock `khds` and `khu` Not in Factory Firmware ROM:**
   - Sending `khds` and `khu` over BLE to `PetoiBLE-4CB5` returned:
     ```text
     Robot -> '?\r\nk\r\n'
     ```
   - `?` is OpenCat's "Unknown Skill" error: `hds` (handstand) and `hu` (hands up) were not compiled into this Bittle's flash instinct table (`InstinctBittleESP.h`), so the robot ignored them even though `ksit`, `kbalance`, `khi`, and `d` worked.
2. **Open-Loop `handstand` / `rearStand` Combos Hit Head & Fell:**
   - Keyframes from `firmware/balanceStand.h` (`handstandEntry` and `rearEntry`) were packaged into `combos.json` as 7-frame `handstand` and `rearStand` (`147` integers, `149` wire bytes) so they could be uploaded via `K` without flashing firmware.
   - `bittle --ble play handstand` executed on the robot, **but the robot did not balance on two legs** — it slammed its head/chin onto the floor, tipped over, and self-righted/came back up.
   - `bittle --ble play rearStand` also did not hold a true rear balance, and on BLE logged `(no confirmation for 'K' - it may still have run)` after the boot banner duplicated (`Init IMU` / `Ready!` printed twice during reconnect).
3. **Why Open-Loop Handstands Fail Physically (Confirmed by `sim/stand_sim.py`):**
   - **No ankle actuators:** Bittle only has shoulder/hip and knee servos. Once the center of mass (COM) passes past the paw edge, the paw becomes an unactuated pivot; rotating the shoulder swings the light airborne leg rather than pushing the body back upright.
   - **Tiny paw contact (`~4 mm`):** `stand_sim.py` gives a static pose balance window of only **`±1°`**.
   - **Bad head angle in raw keyframes:** `handstandEntry` had Joint 0 (head) tilted down at `+85°`, driving the chin into the floor on any forward lean.
   - **Open-loop vs. 200 Hz IMU feedback:** Keyframes cannot sense or counter-steer tilt.

### What Was Built (Partially Tested / Unflashed)
- **`sim/stand_sim.py` (Worked):** Planar simulation comparing paw contact lengths (`4 mm` to `50 mm`) and link latencies (`onboard`, `USB serial`, `BLE`, `WiFi`). Showed that expanding contact (e.g., resting on shins/forearms `50 mm`) widens the static balance window to `±21°`, whereas wireless PID over WiFi fails (`0.0 mN s`) and BLE latency (`~75 ms`) halves shove tolerance (`17.6 mN s` vs `41.0 mN s` onboard).
- **`firmware/balanceStand.h` + `firmware/balance_stand.patch` (Not Flashed):** Written and host-tested on PC (with `BALANCE_STAND_HOST_TEST`), **but never compiled for ESP32 or flashed onto the robot** (Arduino/Espressif toolchains were blocked/not run). Therefore, `bittle stand hand`, `stand rear`, `stand watch`, `stand laptop`, and raw `y*` firmware commands remain **untested on real hardware**.

---

## 4. Untested CLI Transports & Features

- **Real Hardware USB Serial (`--serial /dev/ttyUSB0`), Classic Bluetooth (`--serial /dev/rfcomm0`), and Real WiFi (`--wifi <ROBOT_IP>`):** Tested **only** against `mock_bittle.py`, never against the physical Bittle X.
- **`mix` Command & `bittle_mix.py` CLI Generation:** Works structurally, but requires `--vault <Bittle_Knowledge_Vault>` containing `Actions/Bittle X - <skill>.md` notes. No `Bittle_Knowledge_Vault` directory exists on this computer, so `mix` cannot be run locally without providing the vault.
- **Unresolved Telemetry Probe (`?`, `v`, `g`):** Early BLE probe of `?` timed out (`BleakClient.connect()` `TimeoutError`) before the BLE/boot-sync fixes; full IMU/battery telemetry streaming from real hardware was not captured.

---

## 5. Isaac Sim / Isaac Lab RL Training — **ISAAC LAB TRAINED TO 100% SUCCESS; LEGACY REPO BROKEN; SIM-TO-REAL NOT YET BUILT**

### What Didn't Work
1. **Legacy `Bittle-IsaacSim` (`Dafodilrat/Bittle-IsaacSim`, Isaac Sim 4.5.0):**
   - Its `RL Viewport` Isaac Sim extension (`exts/customView/customView/ext.py`) is broken/deprecated due to Isaac Sim API changes.
2. **Duplicate `ArticulationRootAPI` in Original Bittle USD (`Bittle-IsaacSim/Bittle_URDF/bittle`):**
   - Both `/bittle` and `/bittle/base_frame_link` had `ArticulationRootAPI` applied in `bittle.usd` and `configuration/bittle_physics.usd`, causing Isaac Lab 3.0 / Isaac Sim 6.2 spawning to fail.
3. **Early Short RL Test Runs (5 & 10 Iterations):**
   - `2026-11-14_10-55-20` (5 iters) & `2026-11-14_10-56-31` (10 iters): `Mean reward` was `-5.03` / `-7.08`, `Mean episode length` `60.00` / `106.39`, `Metrics/success_rate: 0.0000`, `Episode_Termination/base_contact: 0.1413` / `0.2780`.
4. **Untrained Rough Terrain & Unbuilt Sim-to-Real Bridge:**
   - `Isaac-Velocity-Rough-Bittle` (`rough_env_cfg.py`) was registered in Isaac Lab, but never trained.
   - Sim-to-Real bridge (streaming Isaac Lab actions via `K`/`o`/`I` tokens to physical Bittle) was architected on paper, **not** implemented or tested on the robot.

### What Worked
1. **USD Asset Fix (`/home/robotics/isaac/bittle_asset/`):**
   - Removed the duplicate `ArticulationRootAPI` from `/bittle/base_frame_link` in `bittle.usd` and `configuration/bittle_physics.usd`, keeping `/bittle` as the sole articulation root.
2. **ARM64 (`aarch64`) NVIDIA GB10 Isaac Lab 3.0 / Isaac Sim 6.2 Execution:**
   - Using `LD_PRELOAD=/lib/aarch64-linux-gnu/libgomp.so.1` and `OMNI_KIT_ACCEPT_EULA=YES` via `uv run isaaclab train` in `/home/robotics/isaac/IsaacLab`.
3. **Converged Flat-Terrain PPO Policy (`2026-11-14_10-57-04`):**
   - **2,048 parallel envs**, **1,500 iterations**, **73,728,000 total steps** in **1,648.86 s** (~27.5 min) at ~`44,739 steps/s`.
   - Final metrics (iter 1499): `Mean reward: 29.46`, `Mean episode length: 1000.00`, `Metrics/success_rate: 1.0000`, `Episode_Termination/base_contact: 0.0000` (0 falls), `error_vel_xy: 0.2285`, `error_vel_yaw: 0.2583` (note: `feet_air_time` stayed slightly negative at `-0.0105`).
   - Saved checkpoint: `/home/robotics/isaac/bittle_training/bittle_policy_final.pt` and exported TorchScript `/home/robotics/isaac/IsaacLab/logs/rsl_rl/bittle_flat/2026-11-14_10-57-04/exported/policy.pt`.
