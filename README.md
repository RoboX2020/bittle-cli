# Bittle Terminal Controller (`bittle-cli`)

A command-line controller, motion fusion engine, mock hardware simulator, and two-leg stand research toolkit for **Petoi Bittle / Bittle X** (OpenCatEsp32) quadruped robots.

This repository also documents the complete end-to-end history of everything built, tested, and simulated for Bittle on this workstation (`spark-a318`, Ubuntu 24.04 `aarch64`), including what worked, what failed, and every related asset/RL pipeline present on the machine.

---

## Detailed Documentation

- **[Worklog: What Worked & What Didn't](docs/WORKLOG_WHAT_WORKED_AND_DIDNT.md)** — Full hardware, BLE, handstand, firmware, and RL findings with exact robot logs and failure analyses.
- **[Handstand, Rear Stand & Firmware Patch](docs/HANDSTAND_AND_FIRMWARE.md)** — Planar physics model (`sim/stand_sim.py`), `firmware/balanceStand.h` (`y` token), flashing guide, and PID tuning.
- **[Isaac Sim & Isaac Lab RL Pipeline](docs/ISAAC_SIM_AND_RL.md)** — USD asset fixes, `Isaac-Velocity-Flat-Bittle` / `Rough` training results on NVIDIA GB10, and Sim-to-Real / Real-to-Sim architecture.
- **[Computer-Wide Bittle Inventory](docs/COMPUTER_INVENTORY.md)** — Map of every Bittle-related file, directory, binary, USD asset, RL checkpoint, and log on this machine.

---

## Repository Layout

| Path | Purpose |
|---|---|
| `bittle_cli.py` | Main CLI & interactive shell (`ble`, `wifi`, `serial`, `scan`, `list`, `play`, `chain`, `mix`, `seq`, `stand`) |
| `bittle_mix.py` | Motion fusion engine (`K` binary array compiler; splices skills up to ESP32's 125-frame buffer limit) |
| `combos.json` | 14 pre-computed fused combos (`flipShow`, `flipFlip`, `boxerCombo`, `handstand`, `rearStand`, etc.) |
| `mock_bittle.py` | Virtual Bittle simulator (WebSocket server on port `8081` + virtual serial PTY `/tmp/ttyBittle`) |
| `test_bittle.py` | Automated 10-test end-to-end verification suite against `mock_bittle.py` |
| `firmware/balanceStand.h` | Custom C++ closed-loop two-leg stand controller for `OpenCatEsp32` (serial token `y`) |
| `firmware/balance_stand.patch` | Patch hooking `balanceStand.h` into `OpenCatEsp32.ino`, `src/OpenCat.h`, and `src/reaction.h` |
| `sim/stand_sim.py` | Side-view planar rigid-body physics simulation for two-leg stand stability & link latency |
| `pyproject.toml`, `setup.py` | Package metadata exposing global `bittle` and `bittle-mock` console entry points |

---

## System Setup

### Linux (Ubuntu / Debian / Raspberry Pi)
1. Install Python 3 and Bluetooth stack:
   ```bash
   sudo apt update && sudo apt install -y python3 python3-pip bluez
   ```
2. Grant user access to USB/Bluetooth serial ports:
   ```bash
   sudo usermod -a -G dialout $USER
   ```
   Log out and log back in for group changes to apply.

### macOS
1. Install Python 3.8+ via Homebrew or the official installer.
2. Grant Bluetooth permission to your terminal under **System Settings → Privacy & Security → Bluetooth**.

### Windows (10 / 11)
1. Install Python 3.8+ with **Add Python to PATH** enabled.
2. Ensure Bluetooth is enabled (BLE uses native WinRT via `bleak`). For USB serial, install CH340 or CP210x drivers if prompted.

---

## Installation

```bash
git clone https://github.com/RoboX2020/bittle-cli.git
cd bittle-cli
pip install -e .
```

*(On Linux distros enforcing PEP 668 externally-managed environments, use a virtualenv or pass `--user --break-system-packages`.)*

This installs two global commands (`bittle` and `bittle-mock`) and depends on `pyserial>=3.5`, `bleak>=0.21.0`, and `websockets>=11.0`.

---

## Usage

### 1. Discover Devices
```bash
bittle scan
```
Lists BlueZ paired/connected BLE devices, nearby BLE advertisements (`_BLE` / `ffe0` / `6e40`), and serial ports (`/dev/ttyUSB*`, `/dev/rfcomm*`, `COM*`).
Close the Petoi mobile app before connecting over BLE, because the robot accepts only one BLE connection at a time.

### 2. Connect (Pick One Link)

| Link | Command | Notes |
|---|---|---|
| **Bluetooth LE** | `bittle --ble` | Connects to first Bittle found (paired in BlueZ or advertising). Pass name/MAC to select one: `bittle --ble PetoiBLE-4CB5` |
| **Classic Bluetooth** | `bittle --serial /dev/rfcomm0` | Pair `…_SSP` device first (`/dev/rfcomm0` Linux, `/dev/tty.<name>_SSP` macOS, `COMx` Windows) |
| **USB Cable** | `bittle --serial /dev/ttyUSB0` | `115200` baud (`COMx` on Windows) |
| **WiFi WebSocket** | `bittle --wifi 192.168.1.42` | Connects to `ws://<ip>:81` with 15 s heartbeat (firmware drops clients after 40 s silence) |

One-time WiFi credential provisioning over USB or BLE:
```bash
bittle --serial /dev/ttyUSB0 wifi-setup "MyWifi" "MyPassword"
```

### 3. Interactive Shell & Direct Commands

Run without a trailing command to enter the Tab-completed shell:
```text
bittle> list                         # show all combos and chains
bittle> play flipShow                # upload and run fused combo (K token)
bittle> play victoryLap              # run chain step-by-step
bittle> chain partyTrick --onboard   # run chain as one robot-side q queue
bittle> play bf                      # run a stock skill (with gyro guard)
bittle> ksit                         # send raw OpenCat command
bittle> gyro off                     # disable gyro auto-recovery (gb)
bittle> gyro on                      # enable gyro auto-recovery (gB)
bittle> stop                         # rest and relax servos (d)
```

Or run single commands directly:
```bash
bittle --ble ksit
bittle --ble play flipShow
bittle --wifi 192.168.1.42 play stuntDog
```

### 4. Compose New Combos & Chains

```text
bittle> mix crazyDog sit hi*2 bf chr zz@40          # requires --vault <Bittle_Knowledge_Vault>
bittle> seq hello ksit:1 khi:0.5 kwkF:2 kbalance:0  # define a timed chain
```
Segment modifiers for `mix`: `*N` (repeat), `~S` (cap speed), `@D` (hold last frame `D * 50 ms`). Gaits (`wkF`, `trF`, etc.) cannot be fused into `K` arrays—use `seq` / `chain` instead. User-created entries save to `my_combos.json` (in the repo dir if writable, cwd, or `~/.config/bittle/my_combos.json`).

### 5. Built-in Safety Features
- **Gyro Auto-Recovery Guard:** Moves involving `VIOLENT` skills (`bf`, `ff`, `flip`, `flipF`, `flipD`, `rl`, `hds`, `jmp`, `rc`, `handstand`, `holdHDS`, `kick`) automatically send `gb` before and `gB` after so firmware self-righting (`rc`) does not abort flips mid-air. Pass `--keep-gyro` to disable this.
- **Command Echo Synchronization:** Serial/BLE waits for the robot to echo the command token before sending the next command.
- **ESP32 Buffer & Seam Checks:** `bittle_mix.py` rejects combos exceeding 125 frames (`BUFF_LEN 2507`) and slows segments whose joint jump exceeds `60°` (unless a gyro trigger is active).

---

## Testing Without Hardware

Run the automated test suite (starts `mock_bittle.py` on WebSocket `ws://127.0.0.1:8089` and virtual serial PTY `/tmp/ttyBittle_test`):
```bash
python3 test_bittle.py
```

Or run the mock robot interactively in two terminals:
```bash
# Terminal 1
bittle-mock

# Terminal 2
bittle --wifi 127.0.0.1:8081
# or
bittle --serial /tmp/ttyBittle
```

---

## Summary of Status: What Worked vs. What Didn't

| Area | Status | Summary |
|---|---|---|
| **Mock Simulator & Test Suite** | Worked | `10/10` tests pass in `test_bittle.py` (offline `list`/`scan`, WebSocket, virtual PTY serial, `K` binary combos, `q` queues). |
| **BLE Control (`PetoiBLE-4CB5`)** | Worked after fixes | Required 3 fixes in `bittle_cli.py`: dynamic Petoi `0000ffe0`/`ffe1` GATT discovery (not just Nordic `6e40`), BlueZ paired/connected device lookup, and waiting for `Ready!` boot banner + `15 ms` chunk pacing. |
| **Stock Postures & `K` Upload over BLE** | Worked | `ksit`, `kbalance`, `gb`/`gB`, and 149-byte `handstand` `K` payload confirmed on hardware. |
| **Stock `khds` / `khu` ROM Skills** | Failed | Not compiled into factory firmware ROM on this Bittle; robot returned `?\r\n k` ("Unknown Skill"). |
| **Open-Loop 2-Leg `handstand` / `rearStand`** | Failed to balance | Robot hits its head/chin on the floor, falls, and recovers. `sim/stand_sim.py` showed 4 mm paw tips give only a `±1°` balance window with no ankle actuators; active 200 Hz IMU control is required. |
| **Custom Firmware (`balanceStand.h`)** | Not yet flashed | Patch applies cleanly and host-test logic exists, but has **not** been compiled for ESP32 or flashed onto the BiBoard; `stand *` (`y` token) is untested on real hardware. |
| **USB Serial / Classic SSP / Real WiFi** | Untested on hardware | Verified only against `mock_bittle.py`. |
| **Isaac Lab RL Locomotion (`Isaac-Velocity-Flat-Bittle`)** | Worked in sim | Trained 1,500 PPO iterations on NVIDIA GB10 (`73.7M` steps) after fixing duplicate `ArticulationRootAPI` in `bittle.usd`; converged to `100%` success rate (`0` falls). Sim-to-Real deployment to physical Bittle is not yet implemented. |

See [docs/WORKLOG_WHAT_WORKED_AND_DIDNT.md](docs/WORKLOG_WHAT_WORKED_AND_DIDNT.md) for the full technical breakdown.
