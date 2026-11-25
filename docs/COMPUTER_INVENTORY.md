# Computer-Wide Bittle Inventory (`spark-a318`)

Every Bittle-related directory, file, binary, asset, RL checkpoint, and log present on this workstation as of `2026-11-25`.

---

## 1. Primary Controller Repository (`/home/robotics/bittle-cli`)
- **GitHub Remote:** `https://github.com/RoboX2020/bittle-cli.git` (`main`)
- **Installed Mode:** Editable `pip install -e .` (`bittle-cli 1.0.0`)
- **Global Binaries:**
  - `/home/robotics/.local/bin/bittle` → `bittle_cli:main_cli`
  - `/home/robotics/.local/bin/bittle-mock` → `mock_bittle:main`
- **User Config Directory:** `/home/robotics/.config/bittle/` (currently empty; stores fallback `my_combos.json`)
- **Files:** `bittle_cli.py`, `bittle_mix.py`, `combos.json`, `mock_bittle.py`, `test_bittle.py`, `firmware/balanceStand.h`, `firmware/balance_stand.patch`, `sim/stand_sim.py`, `pyproject.toml`, `setup.py`, `requirements.txt`, `README.md`, `docs/`

---

## 2. Original Working Folder (`/home/robotics/Downloads/bittle`)
Pre-packaging working directory from `2026-11-13` – `2026-11-14`. Contains:
- `bittle_cli.py`, `bittle_mix.py`, `combos.json`, `mock_bittle.py`, `test_bittle.py`
- `bittle_cli handstand.py` (original handstand branch before its `stand` commands were merged with the BLE `ffe1`/BlueZ fixes into `bittle_cli.py`)
- `README.md`, `README handstand.md` (source documentation consolidated into this repo)
- `balanceStand.h`, `balance_stand.patch`, `stand_sim.py` (copied into `firmware/` and `sim/` in `bittle-cli`)

**Key differences vs. `/home/robotics/bittle-cli`:** `bittle-cli/bittle_cli.py` adds `get_user_file()` fallback (`~/.config/bittle/my_combos.json`), safer `combos.json` path resolution, `main_cli()` entrypoint, and Python packaging files.

---

## 3. Isaac Sim / Isaac Lab Assets & RL Workspaces (`/home/robotics/isaac/`)

| Path | Contents & Purpose |
|---|---|
| `/home/robotics/isaac/bittle_asset/` | Fixed 10×-scale USD stage (`bittle.usd`, `configuration/bittle_base.usd`, `bittle_physics.usd`, `bittle_sensor.usd`) with duplicate `ArticulationRootAPI` removed from `/bittle/base_frame_link`. |
| `/home/robotics/isaac/bittle_asset_real/` | True 1:1 real-scale USD stage (`0.1×` linear geometry/joints/COM, `0.01×` diagonal inertia, `0.271 kg` real mass). |
| `/home/robotics/isaac/bittle_training/` | Turnkey RL scripts (`train.sh`, `play.sh`, `train_handstand.sh`, `play_handstand.sh`, `start_tensorboard.sh`, `README.md`), `custom_env/bittle_env_cfg.py`, training logs, and converged locomotion checkpoint `bittle_policy_final.pt` (`735,925` bytes). |
| `/home/robotics/isaac/IsaacLab/source/isaaclab_tasks/isaaclab_tasks/core/velocity/config/bittle/` | Registered Gym tasks `Isaac-Velocity-Flat-Bittle`, `Isaac-Velocity-Rough-Bittle`, and `Isaac-Handstand-Bittle` (`flat_env_cfg.py`, `rough_env_cfg.py`, `handstand_env_cfg.py`, `handstand_mdp.py`, `agents/rsl_rl_ppo_cfg.py`, `__init__.py`). |
| `/home/robotics/isaac/IsaacLab/logs/rsl_rl/` | Training logs, checkpoints, `params/{agent,env}.yaml`, and TensorBoard `tfevents` across `bittle_flat/`, `bittle_handstand/`, and `bittle_handstand_real/`. |
| `/home/robotics/isaac/Bittle-IsaacSim/` | Legacy `Dafodilrat/Bittle-IsaacSim` clone (Isaac Sim 4.5.0; original `Bittle_URDF/bittle/` USD, `docker-compose.yaml`, `dockerfile`, `launch.py`, screenshots in `images/`, and broken/deprecated `exts/customView/`). |

---

## 4. Physical Robot & Conversation Logs
- **Paired Real Hardware:** `PetoiBLE-4CB5` (`60:33:66:0A:4C:B5`, BlueZ GATT `0000ffe0`/`0000ffe1`)
- **Shell History:** `/home/robotics/.bash_history` contains earlier CLI trials (`bittle scan`, `bittle --ble`, `bittle --ble play hds`, `bittle --serial /dev/ttyUSB0`, `bittle play patrol`).
- **Agent Session Logs (`/home/robotics/.gemini/antigravity-cli/brain/`):**
  - `9859a90b-d339-4691-8f2b-b83113b91941`: Initial CLI setup, mock simulator verification, BLE `ffe1`/BlueZ/boot-banner/15 ms pacing debugging on `PetoiBLE-4CB5`, Sim-to-Real discussion, and `khds`/`khu` + `handstand`/`rearStand` hardware tests.
  - `38d120a5-54e8-47af-8188-59ba9b4a893a`: USD `ArticulationRootAPI` fix, Isaac Lab task registration, and 1,500-iter PPO training run (`2026-11-14_10-57-04`).
  - `90db6bb7-693a-4c9f-ac1a-0900f5565e4d`: Packaging `bittle-cli` and initial GitHub publish to `RoboX2020/bittle-cli`.
