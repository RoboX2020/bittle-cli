# Petoi Bittle Quadruped RL Training in Isaac Sim / Isaac Lab

Turnkey reinforcement learning training workspace for the **Petoi Bittle** 8-DoF quadruped robot using **NVIDIA Isaac Sim 6.2** and **Isaac Lab 3.0** accelerated on the **NVIDIA GB10** GPU with **RSL-RL (PPO)**.

---

## 1. Robot Specifications (Bittle)

- **Kinematics:** 8-DoF quadruped (4 shoulder joints, 4 knee joints).
- **Control Mode:** Position control with PD actuators (simulating high-torque micro-servos).
- **Observation Space:** 36-dimensional state vector (projected gravity, base linear & angular velocity, joint positions & velocities, previous actions, velocity commands).
- **Action Space:** 8-dimensional normalized joint target angles.
- **Physics Solver:** Newton MJWarp / GPU PhysX with sub-millisecond step times.

---

## 2. Directory Layout

```text
/home/robotics/isaac/bittle_training/
├── train.sh                  # Main training launcher (supports flat/rough, parallel envs, viz)
├── play.sh                   # Policy evaluation & playback script
├── start_tensorboard.sh      # TensorBoard telemetry launcher (port 6006)
├── README.md                 # This documentation
└── custom_env/
    └── bittle_env_cfg.py     # Custom reward tuning & environment parameters
```

---

## 3. Quick Start: Training

### A. High-Throughput Headless GPU Training (Default: 2,048 Envs)
```bash
cd /home/robotics/isaac/bittle_training
./train.sh --terrain flat --num_envs 2048 --max_iterations 1500
```

### B. Rough Terrain Training (Boxes, Slopes, Random Heights)
```bash
cd /home/robotics/isaac/bittle_training
./train.sh --terrain rough --num_envs 2048 --max_iterations 1500
```

### C. Live Interactive GUI Simulation (Local Desktop)
```bash
cd /home/robotics/isaac/bittle_training
./train.sh --viz kit --num_envs 16
```

### D. WebRTC Livestreaming to Browser
```bash
cd /home/robotics/isaac/bittle_training
./train.sh --livestream 1 --num_envs 32
```

---

## 4. Policy Playback & Visualization

To evaluate and visualize a trained checkpoint:

```bash
cd /home/robotics/isaac/bittle_training

# Play latest trained checkpoint
./play.sh --checkpoint latest --num_envs 16

# Play with desktop GUI window
./play.sh --checkpoint latest --viz kit --num_envs 4
```

---

## 5. Telemetry & Monitoring

Launch TensorBoard to track rewards, losses, gait stability, and velocity tracking errors:

```bash
cd /home/robotics/isaac/bittle_training
./start_tensorboard.sh
```
Open **`http://localhost:6006`** in your browser.
