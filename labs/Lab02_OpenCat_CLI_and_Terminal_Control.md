# Lab 02: Terminal control, protocols and motion sequences

## Start here
A transport moves bytes. A protocol gives those bytes meaning. A motion sequence adds time. Keep these layers separate when debugging: a missing BLE connection is different from an unknown skill, and both differ from a poorly chosen motion.

## What you will learn
- Use loopback WebSocket and virtual serial links.
- Compare a single command, a timed chain and a binary behavior.
- Diagnose transport failures without making increasingly aggressive hardware tests.

## 1. Run the repository checks
Activate the environment from Lab 01, then run:
```bash
python test_bittle.py
```
The suite starts its own mock on port 8089 and `/tmp/ttyBittle_test`. It exercises listing/scanning, WebSocket commands, chains, binary combos and virtual serial. Read the summary your run prints; do not substitute the author's archived pass count for your own result. Some sample combo names describe stunts, but these automated cases target the mock, not a physical robot.

## 2. Read the wire protocol
A command token is case-sensitive. `k` requests a named built-in skill, `m` changes a joint target, `d` rests the robot, `q` queues timed tasks, and uppercase `K` carries a binary behavior payload. Text and binary framing differ. Consult [Petoi's serial protocol](https://docs.petoi.com/apis/serial-protocol) and the firmware for your board rather than assuming all tokens are implemented on every version.

The CLI accepts raw commands and higher-level helpers. An acknowledgment indicates firmware/mock parsing, not proof that the intended trajectory completed. A `?` can indicate an unknown skill. No response can indicate startup timing, the wrong characteristic, a disconnected link or a firmware issue.

## 3. Compose a modest sequence on the mock
With Lab 01's mock running, open the interactive shell:
```bash
python bittle_cli.py --wifi ws://127.0.0.1:8081
```
Inside the shell, type:
```text
seq greeting ksit:1 khi:0.5 kbalance:1
chain greeting
chain greeting --onboard
stop
quit
```
`seq` defines a saved chain; it does not run it by itself. The normal chain sends steps from the host. `--onboard` submits one firmware task-queue command. Compare the mock log for the two forms and explain what happens if the host link drops between steps. Use a unique name if you already have a saved chain with this name.

Repeat a simple posture through virtual serial:
```bash
python bittle_cli.py --serial /tmp/ttyBittle ksit
```
The transport changed, but the skill token did not. Record which failures belong to each layer.

## 4. Inspect binary behaviors without making one a prerequisite
Open `combos.json` and `bittle_mix.py`. A behavior has a header and frames; frames hold joint angles and timing/control fields. The original implementation has explicit frame-size and seam-handling rules. Compare two adjacent frames and identify the largest angle jump. Explain why a low frame count does not guarantee a gentle motion.

`mix` requires an external Bittle_Knowledge_Vault folder not included here. Use the shipped arrays for protocol study; do not promise that the missing source-skill library is part of this checkout. The gyro guard temporarily disables firmware balancing around certain moves. It is an execution convention, not a safety guarantee.

## 5. Troubleshoot one variable at a time
For real BLE, verify device identity, power, competing connections and initialization first. The author's implementation supports Petoi FFE0/FFE1 and Nordic-style UART discovery, checks paired BlueZ devices and paces writes. Those fixes explain a recorded Linux setup; they are not a reason to edit UUIDs or timing blindly on another board. Use logs, identify the failed layer and reproduce with a non-moving or low-risk command before returning to the manufacturer's motion workflow.

## Check your understanding
- Why does an onboard queue reduce host scheduling dependence without creating closed-loop balance?
- What distinguishes a binary `K` behavior from a host-driven chain?
- Which result would make you stop and inspect firmware instead of retrying motion?

## Submit
Your test output, a host-versus-onboard trace, and a short explanation of a transport/protocol/motion failure. Pass when you can reproduce the mock exercise over both links and explain the limitations.

## Continue
[Lab 03: Import Bittle into Isaac Sim and validate the model](Lab03_URDF_USD_and_Simulation_Setup.md)
