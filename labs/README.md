# Petoi Bittle Robotics Lab Curriculum

A complete, end-to-end hands-on robotics curriculum taking you from unboxing and programming a physical **Petoi Bittle / Bittle X** (`OpenCatEsp32`), through terminal CLI control, URDF/USD modeling, Real-to-Sim and Sim-to-Real bridging, GPU locomotion RL, and 1:1 real-scale **Handstand Reinforcement Learning with Maximum Domain Randomization** in NVIDIA Isaac Lab 3.0.

Every lab references the **actual code, URDF/USD models, images, checkpoints, firmware patches, and hardware/simulation logs** archived in this repository.

---

## Lab Modules

| Lab | Title | Key Artifacts in Repo |
|---|---|---|
| **[Lab 01](Lab01_Initializing_and_Programming_Bittle.md)** | **Initializing & Programming Bittle Normally** | `combos.json`, `firmware/balanceStand.h` |
| **[Lab 02](Lab02_OpenCat_CLI_and_Terminal_Control.md)** | **OpenCat Terminal Control, BLE Debugging & Motion Fusion** | `bittle_cli.py`, `bittle_mix.py`, `mock_bittle.py`, `test_bittle.py`, `cli_data/` |
| **[Lab 03](Lab03_URDF_USD_and_Simulation_Setup.md)** | **URDF, USD Conversion, Scale/Root Fixes & Legacy Isaac Sim** | `assets/urdf/`, `assets/usd_10x/`, `assets/usd_real_1x/`, `assets/images/`, `training/legacy_isaac_sim_4_5/` |
| **[Lab 04](Lab04_Real_to_Sim_and_Sim_to_Real.md)** | **Real-to-Sim System ID & Sim-to-Real Control Bridges** | `sim/stand_sim.py`, `firmware/balanceStand.h`, `firmware/balance_stand.patch`, `bittle_mix.py` |
| **[Lab 05](Lab05_IsaacLab_Locomotion_RL.md)** | **Quadruped Locomotion RL in Isaac Lab (Flat & Rough)** | `training/isaaclab_bittle_config/`, `training/scripts/`, `training/models/locomotion_flat/` |
| **[Lab 06](Lab06_IsaacLab_Handstand_Max_DR.md)** | **1:1 Real-Scale Handstand RL with Max Domain Randomization** | `training/isaaclab_bittle_config/handstand_*.py`, `training/models/handstand_10x/`, `training/models/handstand_real_1x/` |

---

## Repository Data Map (All Computer Data Included)

- **CLI & Firmware:** [bittle_cli.py](../bittle_cli.py), [bittle_mix.py](../bittle_mix.py), [combos.json](../combos.json), [mock_bittle.py](../mock_bittle.py), [test_bittle.py](../test_bittle.py), [firmware/](../firmware/), [sim/stand_sim.py](../sim/stand_sim.py), [cli_data/](../cli_data/)
- **Images & Screenshots:** [assets/images/](../assets/images/) (`IsaacSim.png`, `pyqt_gui.png`, `training.png`, `extension.png`, `bittle_usd_thumb.png`)
- **URDF & Meshes:** [assets/urdf/](../assets/urdf/) (`bittle.urdf`, `bittle.stl`, `meshes/obj/*.obj`, `joint_locs.txt`, `joint_monkey.py`)
- **USD Models:** [assets/usd_10x/](../assets/usd_10x/) (fixed articulation root) and [assets/usd_real_1x/](../assets/usd_real_1x/) (1:1 real-scale `0.1×` linear / `0.01×` inertia)
- **Training Configs, Scripts, Checkpoints & Logs:** [training/](../training/) (`isaaclab_bittle_config/`, `scripts/`, `models/`, `logs/`, `legacy_isaac_sim_4_5/`)
- **Worklog & Inventory:** [docs/](../docs/)
