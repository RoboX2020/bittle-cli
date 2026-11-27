# Petoi Bittle Complete Lab, CLI, URDF/USD & Isaac Lab RL Repository

End-to-end robotics repository for **Petoi Bittle / Bittle X** (`OpenCatEsp32`): terminal controller (`bittle-cli`), motion fusion engine, mock hardware simulator, closed-loop two-leg firmware patch, URDF/USD models, Isaac Sim/Isaac Lab locomotion & **1:1 real-scale Handstand RL with Maximum Domain Randomization**, and a **6-module hands-on Lab Curriculum** containing all data, images, configs, checkpoints, and logs from this workstation.

---

## Instructional Lab Modules ([`labs/`](labs/README.md))

A general learning course from fundamentals to a project. Start with the mock; progress through modeling, tasks, transfer and training. Handstand is an advanced case study, not the prerequisite for every lesson.

- [Lab 01: Robot fundamentals and safe first commands](labs/Lab01_Initializing_and_Programming_Bittle.md)
- [Lab 02: Terminal control, protocols and motion sequences](labs/Lab02_OpenCat_CLI_and_Terminal_Control.md)
- [Lab 03: Import Bittle into Isaac Sim and validate the model](labs/Lab03_URDF_USD_and_Simulation_Setup.md)
- [Lab 04: Build tasks and connect the real robot to simulation](labs/Lab04_Real_to_Sim_and_Sim_to_Real.md)
- [Lab 05: Train and evaluate a locomotion policy](labs/Lab05_IsaacLab_Locomotion_RL.md)
- [Lab 06: Project studio: sim-to-real, with handstand as a case study](labs/Lab06_IsaacLab_Handstand_Max_DR.md)

---

## Repository Contents (All Computer Data Included)

| Path | Contents |
|---|---|
| `bittle_cli.py`, `bittle_mix.py`, `combos.json` | Main CLI controller (`--ble`, `--wifi`, `--serial`, `scan`, `list`, `play`, `chain`, `mix`, `seq`, `stand`), fusion compiler, 14 combos |
| `mock_bittle.py`, `test_bittle.py` | WebSocket + PTY virtual serial simulator and 10-test automated suite |
| `firmware/` | Custom closed-loop stand controller (`balanceStand.h`) & `OpenCatEsp32` patch (`balance_stand.patch`) |
| `sim/stand_sim.py` | Planar rigid-body physics model for two-leg stand stability & link latency |
| `cli_data/` | Archived pre-merge CLI files and original READMEs (`README_downloads_original.md`, `README_handstand_original.md`) |
| `assets/images/` | Isaac Sim, PyQt5 GUI, training, extension, and USD thumbnail screenshots |
| `assets/urdf/` | Complete `Bittle_URDF` (`bittle.urdf`, `bittle.stl`, `.obj` meshes, `joint_locs.txt`, `joint_monkey.py`) |
| `assets/usd_10x/` & `assets/usd_real_1x/` | Fixed 10× USD and true 1:1 real-scale (`0.1×` linear / `0.01×` inertia / `0.271 kg`) USD stages |
| `training/isaaclab_bittle_config/` | Complete Isaac Lab 3.0 task, MDP, reward, and PPO runner configs (`flat`, `rough`, `handstand`) |
| `training/scripts/` | `train.sh`, `play.sh`, `train_handstand.sh`, `play_handstand.sh`, `start_tensorboard.sh` |
| `training/models/` | Checkpoints, TorchScript `policy.pt`, `params/{agent,env}.yaml`, and TensorBoard `tfevents` (`locomotion_flat`, `handstand_10x`, `handstand_real_1x`) |
| `training/logs/` | Compact training metric summaries for locomotion flat, 10× handstand, and 1:1 real-scale handstand |
| `training/legacy_isaac_sim_4_5/` | Legacy Isaac Sim 4.5.0 Docker/PyQt5/extension code (`Bittle-IsaacSim`) |
| `docs/` | Detailed [Worklog (What Worked & What Didn't)](docs/WORKLOG_WHAT_WORKED_AND_DIDNT.md), [Handstand & Firmware](docs/HANDSTAND_AND_FIRMWARE.md), [Isaac Sim & RL](docs/ISAAC_SIM_AND_RL.md), [Computer Inventory](docs/COMPUTER_INVENTORY.md) |

---

## Quick Start

### 1. Install `bittle-cli`
```bash
git clone https://github.com/RoboX2020/bittle-cli.git
cd bittle-cli
pip install -e .
```
- **Linux prerequisites:** `sudo apt update && sudo apt install -y python3 python3-pip bluez` and `sudo usermod -a -G dialout $USER`.
- **macOS:** Grant Bluetooth permission to Terminal under **System Settings → Privacy & Security → Bluetooth**.
- **Windows:** Python 3.8+ in `PATH`; CH340/CP210x drivers for USB serial; Bluetooth enabled for WinRT BLE.

### 2. Test Without Hardware
```bash
python3 test_bittle.py
```

### 3. Control Real Bittle
```bash
bittle scan                       # discover BlueZ paired/advertising BLE & serial ports
bittle --ble                      # interactive BLE shell (Petoi FFE0/FFE1 & Nordic 6E40)
bittle --ble play flipShow        # run fused combo with automatic gb/gB gyro guard
bittle --serial /dev/ttyUSB0      # USB serial (115200 baud)
bittle --wifi 192.168.1.42        # WebSocket ws://<ip>:81
```

---

## Summary of What Worked vs. What Didn't

- **Worked:** `mock_bittle.py` + `test_bittle.py` (`10/10`); BLE control of `PetoiBLE-4CB5` after adding `0000ffe0/ffe1` discovery, BlueZ paired-device lookup, `Ready!` boot-banner sync, and `15 ms` chunk pacing; `Isaac-Velocity-Flat-Bittle` (`100%` success, `0` falls over `73.7M` steps); `Isaac-Handstand-Bittle` (`model_4700.pt` achieved `83%` MAX-DR hold rate and `98.4%` clean front-leg support); 1:1 real-scale `usd_real_1x` + symmetric knee pose (`0.0000 N` shoulder contact).
- **Didn't Work / Pending:** Stock `khds`/`khu` missing from factory ROM (`?\r\n k`); open-loop `handstand` combo slammed head due to `4 mm` paw tips (`±1°` window) and no ankles; `firmware/balanceStand.h` is not yet compiled/flashed on ESP32; legacy Isaac Sim 4.5.0 extension (`ext.py`) is broken; 1:1 real-scale IMU-only handstand RL (`bittle_handstand_real`) is actively training and not yet deployed to physical hardware.

See [docs/WORKLOG_WHAT_WORKED_AND_DIDNT.md](docs/WORKLOG_WHAT_WORKED_AND_DIDNT.md) and [`labs/`](labs/README.md) for full details.
