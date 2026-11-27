# Lab 05: Train and evaluate a locomotion policy

## Start here
Reinforcement learning learns a policy from interaction. The environment supplies an observation, the policy produces an action, physics advances, and a reward describes how useful that transition was. PPO is the optimizer used by this repository's RSL-RL configurations. Start by proving the environment works, then train a small run, then evaluate a fixed checkpoint.

## What you will learn
- Register and discover the existing Bittle tasks in a compatible Isaac Lab workspace.
- Run a small smoke test before a full training job.
- Separate training reward, evaluation metrics and hardware performance.

## 1. Set up a compatible workspace
Install Isaac Lab using its [official quickstart](https://isaac-sim.github.io/IsaacLab/main/source/isaaclab/quickstart.html) and system requirements for the version you selected in Lab 03. Record the Isaac Lab commit/release, Isaac Sim version when used, backend, Python, driver and GPU. The repository's shell wrappers hardcode the author's `/home/robotics` paths and ARM64 preload. They are reference scripts, not a portable installer.

The author's task package lived at `source/isaaclab_tasks/isaaclab_tasks/core/velocity/config/bittle/`. For a matching source tree, copy the complete `training/isaaclab_bittle_config/` directory there only if the destination does not already exist. Keep an existing package and compare rather than overwrite it. If your release has a different task layout/import API, port the package following that release's task-extension pattern before continuing. This course does not claim a copy into arbitrary Isaac Lab versions is sufficient.

For the matching archived source layout, the following preparation is deliberately non-destructive:
```bash
# Set these to your actual local checkouts first.
export BITTLE_REPO=/absolute/path/to/bittle-cli
export ISAACLAB_ROOT=/absolute/path/to/IsaacLab
export BITTLE_TASK_DIR="$ISAACLAB_ROOT/source/isaaclab_tasks/isaaclab_tasks/core/velocity/config/bittle"
# Inspect the parent first. Continue only if this is the matching source layout.
ls "$ISAACLAB_ROOT/source/isaaclab_tasks/isaaclab_tasks/core/velocity/config"
test ! -e "$BITTLE_TASK_DIR" && cp -a "$BITTLE_REPO/training/isaaclab_bittle_config" "$BITTLE_TASK_DIR"
```
If `test` fails, the existing package is left unchanged. Compare it manually. Registration also requires Isaac Lab to import this package; the matching task tree's discovery mechanism must include it. Use the task list in the next step as the check, not a successful copy command alone.

Edit your local task configuration's `usd_path` to an absolute path for the intended asset. Preserve the entire USD directory/reference structure. The flat/rough archived task expects the legacy larger asset; reproducing that experiment and making a new real-scale task are different activities. Recheck the scale/actuator contract from Lab 04 before either.

## 2. Discover and smoke-test
From your compatible Isaac Lab repository root, use the documented CLI:
```bash
uv run isaaclab list_envs --show_presets
uv run isaaclab train --help
```
Confirm `Isaac-Velocity-Flat-Bittle` is listed. If it is absent, fix package discovery/import errors first; more training iterations cannot repair an unregistered task. Check your version's available selectors and dependencies rather than adding undocumented flags.

Run zero actions in one environment to inspect spawning/contacts:
```bash
uv run isaaclab zero_agent --task Isaac-Velocity-Flat-Bittle --num_envs 1 --viz newton
```
Use the visualizer/backend supported by your installed task/release. Check the help/list output if `newton` is unavailable. Do not treat an exception, NaN state or exploding articulation as a training problem.

Then run a short training smoke test:
```bash
uv run isaaclab train --rl_library rsl_rl --task Isaac-Velocity-Flat-Bittle --num_envs 64 --max_iterations 5
```
Record startup errors, finite observations/actions/rewards, episode resets and whether logs/checkpoints appear. A five-iteration run verifies plumbing, not learned walking. Reduce environments for memory limits; do not assume the author's 2048 environments fit your GPU.

## 3. Train a baseline
Once the small run works, choose a compute budget and run:
```bash
uv run isaaclab train --rl_library rsl_rl --task Isaac-Velocity-Flat-Bittle --num_envs 2048 --max_iterations 1500
```
This reproduces the author's configured scale/count only on a compatible, adequately provisioned machine. Save the resolved environment/agent config, seed, source commit and run directory. Keep default settings for the first baseline; change one factor per comparison. Stop for non-finite values, sustained instability or uncontrolled resource use.

The current quickstart uses `uv run isaaclab`; older releases may use different launch scripts. Do not combine commands across release lanes. The archived wrapper additionally sets `LD_PRELOAD` to an aarch64 library. That path must not be copied onto an x86 machine.

## 4. Evaluate a fixed checkpoint
Point playback at the actual checkpoint produced by your run:
```bash
# Replace this example path with the checkpoint you actually saved.
uv run isaaclab play --rl_library rsl_rl --task Isaac-Velocity-Flat-Bittle --checkpoint /absolute/path/to/model.pt --num_envs 4 --viz kit
```
`kit` requires the compatible Isaac Sim integration; use a supported visualizer for your installation. First replay in simulation. Never send this simulation policy straight to servo channels.

Define evaluation before looking at results: command range, episode duration, number of episodes/seeds, reset distribution and failure definition. Measure tracking error, completion duration, falls/contact failures and action saturation. Compare an untrained/zero-action baseline. Report a metric's denominator and conditions. Training reward increasing does not prove sim-to-real transfer.

## 5. Read the author's experiment as a worked example
The archived flat run reports mean reward 29.46 and a logged success-rate metric of 1.0000 after 1500 iterations; its checkpoint/configs/logs are in `training/models/locomotion_flat/` and `training/logs/`. These are the author's recorded results for that setup, not a promised learner outcome or a claim of physical walking. Rough terrain is a registered extension in the original lesson, not an automatic result of flat training.

## Submit
A version manifest, task-discovery result, smoke-test log, checkpoint path and evaluation table. If you lack the GPU/runtime, submit a source/config and archived-log analysis clearly labeled as analysis, not a new training run.

## Continue
[Lab 06: Project studio: sim-to-real, with handstand as a case study](Lab06_IsaacLab_Handstand_Max_DR.md)
