# Bittle: from robot basics to a working project

Learn Bittle as a general robotics platform: understand the mechanism, control it through a terminal, build and validate its simulation model, define tasks, train a policy and plan a measured transfer to hardware. Handstand appears at the end as an advanced project case study, not the premise of the course.

## How to use this course
Work through the six labs in order. Each has explanations, guided practice and a concrete submission. Start with the mock. Move to simulation only after the command/model interfaces make sense, and treat physical actuation as a separate supervised gate.

- **Computer-only route:** Labs 01-02 use the mock. Labs 03-06 can be studied through models, source and archived logs; label that work as analysis when you do not run the simulator.
- **Simulation route:** a compatible Isaac Sim/Isaac Lab installation and GPU are needed for the relevant import/training exercises. Record versions and adapt the author's workstation paths.
- **Hardware route:** requires the correct robot/firmware, manufacturer calibration, safe support and supervision. A simulator or mock pass is not permission to run a stunt.

## Learning path
1. [Lab 01: Robot fundamentals and safe first commands](Lab01_Initializing_and_Programming_Bittle.md)
2. [Lab 02: Terminal control, protocols and motion sequences](Lab02_OpenCat_CLI_and_Terminal_Control.md)
3. [Lab 03: Import Bittle into Isaac Sim and validate the model](Lab03_URDF_USD_and_Simulation_Setup.md)
4. [Lab 04: Build tasks and connect the real robot to simulation](Lab04_Real_to_Sim_and_Sim_to_Real.md)
5. [Lab 05: Train and evaluate a locomotion policy](Lab05_IsaacLab_Locomotion_RL.md)
6. [Lab 06: Project studio: sim-to-real, with handstand as a case study](Lab06_IsaacLab_Handstand_Max_DR.md)

## What changes from the original project notes
The lessons now teach reusable concepts before explaining repository-specific details. They add scaffolded exercises, acceptance checks, version/setup guidance and a project choice. The original six lessons are preserved outside the published course as project records. Their reported results have not been erased or turned into promised learner outcomes.

The repository's code, models, firmware and training runs remain the author's work. The course does not claim that every archived script is portable, that a simulated actor is a finished hardware bridge, or that an older pending status is current. Use the source/configuration belonging to your exact checkpoint.

## Documentation and image credits
- [Petoi joint index](https://docs.petoi.com/petoi-robot-joint-index) and [joint calibration](https://docs.petoi.com/joint-calibration).
- [Petoi serial protocol](https://docs.petoi.com/apis/serial-protocol).
- [NVIDIA URDF import tutorial](https://docs.isaacsim.omniverse.nvidia.com/latest/importer_exporter/import_urdf.html) and [importer reference](https://docs.isaacsim.omniverse.nvidia.com/latest/importer_exporter/ext_isaacsim_asset_importer_urdf.html).
- [Isaac Lab quickstart](https://isaac-sim.github.io/IsaacLab/main/source/isaaclab/quickstart.html).

Documentation images are credited beside their use. The NVIDIA importer screenshot depicts UR10 controls, explicitly not a Bittle import result. The supplied Bittle simulator image is a historical repository screenshot, not evidence of a new run.
