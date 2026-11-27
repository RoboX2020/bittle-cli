# Lab 04: Build tasks and connect the real robot to simulation

## Start here
An imported robot is an asset. A task adds a world, observations, actions, objectives, resets and stop conditions. Real-to-sim means using measurements from the physical system to improve those choices; it is more than showing live robot motion in a viewport.

## What you will learn
- Turn a validated articulation into a task specification.
- Build a joint/unit/timing interface contract.
- Design conservative system-identification and telemetry experiments.

## 1. Specify a task before coding
Start with four-foot standing or flat-ground velocity tracking, not an inverted balance challenge. Write down: terrain, initial pose, desired behavior, allowed contacts, time limit and measurable failure conditions. For velocity tracking, the desired command and measured body velocity differ; that difference is a tracking error. A reward is a training signal, not automatically a success metric.

Use this interface contract:
- **Asset:** USD path, scale, mass and joint names from Lab 03.
- **Actions:** eight joint targets or offsets, their order, units, scale, neutral pose and clamp limits.
- **Observations:** available sensors, frame, units, normalization and history length.
- **Timing:** simulation step, control step, communication delay and timeout behavior.
- **Resets:** safe initial state and termination reasons, including invalid physics.

## 2. Read the existing Isaac Lab task
Open `training/isaaclab_bittle_config/__init__.py`, then `rough_env_cfg.py`, `flat_env_cfg.py` and `agents/rsl_rl_ppo_cfg.py`. Registration binds a task ID to an environment class and an RL runner. The flat configuration inherits the rough configuration and removes terrain/height-scan features. Follow those imports instead of copying only the shortest file.

Locate the scene robot, actuator settings, observation group, reward terms, commands, reset events and terminations. Create a one-page map from each concept to its file/class. Modify a copy for experiments. Keep the original task as your baseline.

The supplied locomotion configuration references the larger asset, uses a 0.58 m target standing height and 15 N m effort limit. Those are that archived simulation's settings, not instructions for the real Bittle. The handstand configuration uses the real-scale asset and a different actuator/pose setup. Do not mix a real-scale USD with the legacy values and call it a validated model.

## 3. Map real and simulated joints
Use this name mapping, then verify signs and offsets on your own asset:
```text
8  left_front_shoulder_joint
9  right_front_shoulder_joint
10 right_back_shoulder_joint
11 left_back_shoulder_joint
12 left_front_knee_joint
13 right_front_knee_joint
14 right_back_knee_joint
15 left_back_knee_joint
```
A conversion is more than `radians * 180 / pi`. It also needs the correct permutation, direction sign, calibration offset and allowed range for each joint. Write a table with all of those columns. First test the mapping in simulation and the mock. Physical single-joint checks require the manufacturer's calibration/support procedure, small approved motion and supervision.

## 4. Bring measurements into simulation
Record the robot/firmware identity, geometry, battery condition, surface, payload and measurement method. For a supported, conservative target step, log command time and any actual measured response. Do not infer joint position feedback merely because a command was acknowledged: verify what the board exposes. Log timestamps and units for IMU samples and note the coordinate frame.

Compare repeated trials to a model: dead time before response, rise/settling behavior, saturation and steady error. Keep measured values separate from estimated parameters. Change one model parameter at a time and test on a different trial. A parameter fitted to one movement is not universal identification.

The author's two-leg planar model is available as an optional sensitivity exercise:
```bash
python sim/stand_sim.py --links
```
Vary contact size or communication assumptions in a separate copy and compare stability. This reduced model teaches delay/contact sensitivity; its numbers do not establish your robot's safe operating envelope.

## 5. Use feedback, not just playback
In open loop, targets follow a schedule regardless of measured error. In closed loop, observations affect the next command. Network delay changes when those observations and commands matter. A mirrored digital twin can display state without controlling the physical robot at all; describe whether your link is observation-only, command-only or bidirectional.

Before a bidirectional bridge, define message schema, frame transforms, timestamp handling, dropped-packet policy, target clamps, watchdog and stop behavior. Begin with replayed logs, then live observation-only telemetry. Hardware actuation is a later gate, not a default side effect of connecting a dashboard.

## Worked interface example: a log before a live bridge
Use a CSV log with columns `host_time_s,robot_time_ms,pitch_deg,roll_deg,source`. Keep the original sensor values and record the sign/frame convention. A learner-created bridge can replay these samples to a visual marker in simulation first. Do not overwrite the simulated robot state and then describe that display as a validated dynamics model.

For actions, an example conversion contract is:
```python
# Interface sketch, not a complete hardware controller.
# q_rad is a simulation joint angle in the declared joint order.
# Fill sign, zero_deg and limits from your own verified mapping.
q_deg = q_rad * 180.0 / math.pi
servo_deg = sign * q_deg + zero_deg
servo_deg = max(min_deg, min(max_deg, servo_deg))
```
Apply a separate rate limit between the previous target and this target. Check finite values, stale timestamps and joint count before conversion. Reject a malformed observation instead of continuing with old data. Unit-test a neutral pose, a small positive angle, a reversed joint and an out-of-range target entirely offline.

The repository contains transport and stand-controller experiments, not a universal plug-and-play ROS/Isaac bridge. In a live implementation, the transport receiver should only update a timestamped buffer; the control tick should consume one consistent snapshot. Log received data and computed targets before enabling any outgoing actuation. This makes observation-only mirroring a concrete first milestone, while keeping a learned controller's deployment a separate engineering task.

## Submit
A task sheet, joint-interface table and a real-to-sim experiment plan or measured log with explicit sensor limits. Pass when the chosen action/observation contract can be implemented without inventing unavailable sensors or silently changing scale.

## Continue
[Lab 05: Train and evaluate a locomotion policy](Lab05_IsaacLab_Locomotion_RL.md)
