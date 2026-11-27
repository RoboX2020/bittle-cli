# Lab 06: Project studio: sim-to-real, with handstand as a case study

## Start here
A final project combines the course's interfaces and evidence. Choose a behavior you can specify, test and explain. Handstand is one advanced worked example in this repository, not a requirement for understanding Bittle or completing the foundational course.

## Choose a project
- **Control project:** a bounded posture/greeting sequence with a mock regression test and a documented hardware preflight.
- **Simulation project:** a reproducible velocity-tracking evaluation or a carefully scoped terrain/actuator study.
- **Transfer project:** an observation-only real-to-sim telemetry bridge, followed by a separately validated actuator interface.
- **Advanced research project:** real-scale handstand training with explicit contacts, failure rules and robustness tests.

Choose the scope before running. A strong project can end with a well-supported simulation result or a demonstrated transfer limitation. Hardware stunt success is not the grading criterion.

## 1. Write an acceptance test
State the behavior, starting conditions, allowed sensor inputs, action representation and completion/failure criteria. Separate nominal tests from disturbances. List what must be observed, not merely rewarded. Keep training and held-out evaluation configurations distinct. Save the commit, asset version, seed and checkpoint used for each result.

## 2. Connect simulation to reality in stages
A trained actor is not a complete robot controller. The deployment pipeline needs all of the following:
1. Load a checkpoint/export compatible with the policy architecture. Match input order, history length, normalization and output scaling exactly.
2. Reproduce observations with real sensors in the correct body frame and units. Do not replace unavailable simulated velocity/joint measurements with zeros and assume equivalence.
3. Convert the action to calibrated servo targets using Lab 04's permutation/sign/offset table and limits.
4. Run at a measured control period. Log sensor/command timestamps, latency, stale data and deadline misses.
5. Enforce target/rate clamps, communication watchdog and a validated stop/fall response outside the learned policy.

Begin with offline replay: feed recorded observations to the actor and inspect its outputs without a robot connection. Next run a mock/dry interface, then observation-only live telemetry. Only after those checks consider supervised, supported, low-risk hardware tests. Use the board-specific manufacturer's procedure, protect people/equipment and stop on unexpected motion. Relaxing servos may cause collapse; it is not equivalent to a mechanical safety system.

## 3. Open-loop export versus closed-loop policy
An open-loop `K` behavior samples a trajectory and plays it back. It can demonstrate motion encoding but cannot correct a new disturbance from current observations. A closed-loop policy requires fresh observations and computation on the host or onboard system. BLE compatibility alone does not make either strategy suitable for a balance controller.

For IMU-only deployment, design/train an actor whose inputs really are available. A privileged critic can use simulation-only state during training, while the actor cannot depend on it at deployment. The original handstand lesson records a 56-dimensional IMU/action-history actor and a privileged critic. Inspect the resolved configuration for the checkpoint you actually use; a matching filename is not proof of matching tensors.

## 4. Worked capstone: handstand in simulation
The supplied `Isaac-Handstand-Bittle` task shows how a project changes the general task components:
- Orientation target: gravity projected into the body frame distinguishes upright from inverted posture.
- Contacts: front-paw support is not the same as resting on the head, knees or forearms.
- Reward design: relative rear-body height discourages collecting reward by jumping the entire robot upward.
- Numerical stability: bounded penalties and suitable light-robot physics parameters matter before long training.
- Randomization: vary plausible mass, friction, actuator and sensing conditions, then evaluate separately on clean and perturbed cases.

Read `handstand_env_cfg.py`, `handstand_mdp.py` and the original case study. The current source and historical notes may describe different development stages; keep each claim tied to its commit/checkpoint. Do not overwrite the author's running work or treat a historical pending item as current hardware status.

With the matching task installed and real-scale asset checked, use a small run first:
```bash
uv run isaaclab train --rl_library rsl_rl --task Isaac-Handstand-Bittle --num_envs 64 --max_iterations 5
```
Then select your own budget and evaluate a fixed checkpoint using the Lab 05 playback pattern with the handstand task ID. Do not begin with the historical million-iteration continuous command. A real-scale simulation checkpoint still needs the transfer gates above.

## 5. Report evidence and limitations
For a simulation project, report episode count/duration, strict success definition, contact failures and disturbance settings. For a bridge, report measured timing and the commands/sensors actually connected. For hardware, distinguish a commanded pose, a completed motion and closed-loop disturbance recovery. Never infer one from another.

Preserve negative results. If performance fails when friction, contact geometry or latency changes, explain the mechanism and the next experiment. More randomization is not automatically better; justify each range with measurements or a stated hypothesis.

## Submit
A project brief, reproducible configuration/commands, evaluation table, a short visual record and a transfer/safety limitations section. Include an interface diagram and a clear statement of which stages were actually run. Handstand results can be discussed as the author's case study even when your own project is a different behavior.

## Continue
Return to the [course overview](README.md) and assemble your project report.

## Original project reference
The original lesson is preserved as a dated project record, including its commands, observations and experimental results: [read the original Lab 06](reference/Lab06_IsaacLab_Handstand_Max_DR.md). Historical status statements belong to that record, not a live hardware assessment.
