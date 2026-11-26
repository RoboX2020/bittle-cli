#!/usr/bin/env python3
"""USB-tethered 50 Hz Option 2 Closed-Loop Handstand Deployment for Petoi Bittle (NyBoard / OpenCat).

Runs the trained 1:1 real-scale Isaac Lab policy (model_2499.pt / policy.pt) on the host workstation,
reading 14-byte binary IMU packets (gravity + gyro) from Bittle over USB serial (/dev/ttyUSB0 @ 115200)
and streaming 8-DoF OpenCat joint targets ('U' + 8*int8 + '~') back at 50 Hz.

Safety workflow:
  1. --mode pose-test : Moves gently to the RL standing pose (0° shoulders, +23° knees) to verify joint signs.
  2. --mode dry-run   : Streams IMU & runs the policy in real time WITHOUT actuating servos (hold in hand & tilt).
  3. --mode live      : Runs full 50 Hz closed-loop handstand on a padded mat with roll/flip fall-catch.
"""
import argparse
import math
import struct
import sys
import time
from collections import deque
from pathlib import Path

import numpy as np
import serial
import torch

DEFAULT_POLICY = (
    "/home/robotics/isaac/IsaacLab/logs/rsl_rl/bittle_handstand_real/"
    "2026-11-25_16-33-26/exported/policy.pt"
)
DEFAULT_CKPT = (
    "/home/robotics/isaac/IsaacLab/logs/rsl_rl/bittle_handstand_real/"
    "2026-11-25_16-33-26/model_2499.pt"
)

# Policy action output order (0..7) -> OpenCat joint channels (8..15)
# Isaac Lab order: LB_sh, LB_kn, LF_sh, LF_kn, RB_sh, RB_kn, RF_sh, RF_kn
OPENCAT_INDICES = [11, 15, 8, 12, 10, 14, 9, 13]
OPENCAT_SIGNS = np.array([1.0, 1.0, 1.0, 1.0, -1.0, -1.0, -1.0, -1.0], dtype=np.float32)
DEFAULT_JOINT_POS_RAD = np.array([0.0, 0.4, 0.0, 0.4, 0.0, -0.4, 0.0, -0.4], dtype=np.float32)
ACT_SCALE = 0.4
ACT_CLIP = 4.0

# NyBoard OpenCat Bittle hardware angle limits for channels 8..15 (deg), capped within +/-125 to avoid '~' (126)
LIMITS_CH8_15 = {
    8: (-125, 80),
    9: (-125, 80),
    10: (-80, 125),
    11: (-80, 125),
    12: (-80, 125),
    13: (-80, 125),
    14: (-80, 125),
    15: (-80, 125),
}

PKT_HEADER = b"\xaa\x55"
PKT_LEN = 14  # 2-byte header + 6 x int16_t (<hhhhhh)
GYRO_LSB_PER_DEGS = 16.4  # MPU6050 DMP @ +/-2000 deg/s


def load_policy(path: Path):
    """Load either exported TorchScript policy.pt or RSL-RL checkpoint model_*.pt."""
    if path.name.startswith("model_") and path.suffix == ".pt":
        ckpt = torch.load(str(path), map_location="cpu", weights_only=False)
        sd = ckpt["actor_state_dict"]
        mean = sd["obs_normalizer._mean"]
        std = sd["obs_normalizer._std"] + 1.0e-2
        w0, b0 = sd["mlp.0.weight"], sd["mlp.0.bias"]
        w2, b2 = sd["mlp.2.weight"], sd["mlp.2.bias"]
        w4, b4 = sd["mlp.4.weight"], sd["mlp.4.bias"]
        w6, b6 = sd["mlp.6.weight"], sd["mlp.6.bias"]
        elu = torch.nn.ELU()

        def infer(obs_np: np.ndarray) -> np.ndarray:
            with torch.no_grad():
                x = (torch.from_numpy(obs_np).unsqueeze(0) - mean) / std
                x = elu(x @ w0.T + b0)
                x = elu(x @ w2.T + b2)
                x = elu(x @ w4.T + b4)
                out = torch.clamp(x @ w6.T + b6, -ACT_CLIP, ACT_CLIP)
                return out.squeeze(0).numpy()

        return infer

    ts = torch.jit.load(str(path), map_location="cpu")
    ts.eval()

    def infer_ts(obs_np: np.ndarray) -> np.ndarray:
        with torch.no_grad():
            x = torch.from_numpy(obs_np).unsqueeze(0)
            out = torch.clamp(ts(x), -ACT_CLIP, ACT_CLIP)
            return out.squeeze(0).numpy()

    return infer_ts


def imu_to_usd(grav_raw: tuple[int, int, int], gyro_raw: tuple[int, int, int]) -> tuple[np.ndarray, np.ndarray]:
    """Convert OpenCat MPU6050 (world_up_imu * 10000, gyro_raw @ 2000dps) to bittle.usd frame."""
    ux, uy, uz = grav_raw[0] / 10000.0, grav_raw[1] / 10000.0, grav_raw[2] / 10000.0
    n = math.sqrt(ux * ux + uy * uy + uz * uz)
    if n > 1e-6:
        ux, uy, uz = ux / n, uy / n, uz / n
    else:
        ux, uy, uz = 0.0, 0.0, 1.0

    # OpenCat IMU (+X=head, +Y=left, +Z=up) -> USD (+X=right, +Y=head, +Z=up)
    proj_grav_usd = np.array([uy, -ux, -uz], dtype=np.float32)

    deg2rad = math.pi / 180.0
    wx_imu = (gyro_raw[0] / GYRO_LSB_PER_DEGS) * deg2rad
    wy_imu = (gyro_raw[1] / GYRO_LSB_PER_DEGS) * deg2rad
    wz_imu = (gyro_raw[2] / GYRO_LSB_PER_DEGS) * deg2rad
    ang_vel_usd = np.array([-wy_imu, wx_imu, wz_imu], dtype=np.float32)
    return ang_vel_usd, proj_grav_usd


def action_to_opencat_8(act: np.ndarray) -> list[int]:
    """Map 8-dim policy output (Isaac joint order) to OpenCat channels 8..15 signed int8 degrees."""
    q_rad = DEFAULT_JOINT_POS_RAD + ACT_SCALE * act
    q_deg = np.degrees(q_rad) * OPENCAT_SIGNS
    oc_map = {}
    for policy_idx, oc_ch in enumerate(OPENCAT_INDICES):
        lo, hi = LIMITS_CH8_15[oc_ch]
        val = int(round(float(q_deg[policy_idx])))
        oc_map[oc_ch] = max(lo, min(hi, val))
    return [oc_map[ch] for ch in range(8, 16)]


def wait_for_ready(ser: serial.Serial, timeout: float = 8.0) -> str:
    t0 = time.monotonic()
    buf = ""
    while time.monotonic() - t0 < timeout:
        chunk = ser.read(256).decode(errors="replace")
        if chunk:
            buf += chunk
            if "Ready!" in buf:
                time.sleep(1.0)
                buf += ser.read(512).decode(errors="replace")
                break
    return buf


def read_imu_packet(ser: serial.Serial, rx_buf: bytearray, timeout: float = 0.2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        idx = rx_buf.find(PKT_HEADER)
        if idx >= 0:
            if idx > 0:
                del rx_buf[:idx]
            if len(rx_buf) >= PKT_LEN:
                pkt = bytes(rx_buf[2:PKT_LEN])
                del rx_buf[:PKT_LEN]
                vals = struct.unpack("<hhhhhh", pkt)
                return vals[:3], vals[3:]
        n_wait = ser.in_waiting
        chunk = ser.read(n_wait if n_wait > 0 else 1)
        if chunk:
            rx_buf.extend(chunk)
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", default="/dev/ttyUSB0")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--policy", type=Path, default=Path(DEFAULT_POLICY))
    ap.add_argument("--mode", choices=["pose-test", "dry-run", "live", "replay"], required=True)
    ap.add_argument("--traj", type=Path, default=Path(__file__).resolve().parent / "training" / "rl_handstand_traj_50hz.npy")
    ap.add_argument("--duration", type=float, default=10.0, help="Seconds for dry-run or live rollout")
    ap.add_argument("--catch", action="store_true", default=True, help="Auto four-leg catch (kup) if rolled/flipped")
    ap.add_argument("--no-catch", action="store_false", dest="catch")
    args = ap.parse_args()

    infer = load_policy(args.policy)
    print(f"[deploy] Loaded policy: {args.policy}")
    print(f"[deploy] Connecting to {args.port} @ {args.baud} ...")

    with serial.Serial(args.port, args.baud, timeout=0.02) as ser:
        boot = wait_for_ready(ser)
        if "Ready!" not in boot:
            print(f"[deploy] Warning: did not see 'Ready!' banner (got {boot[-120:]!r})")
        else:
            print("[deploy] Robot Ready!")

        ser.reset_input_buffer()

        if args.mode == "pose-test":
            print("[deploy] Moving smoothly to RL standing pose (0° shoulders, +23° knees)...")
            ser.write(b"y0\n")
            time.sleep(1.5)
            print(ser.read(512).decode(errors="replace"))
            input("Inspect leg pose, then press Enter to rest servos ('d')...")
            ser.write(b"d\n")
            time.sleep(0.5)
            return

        if args.mode == "replay":
            traj = np.load(str(args.traj))
            print(f"[deploy] Replaying {len(traj)} open-loop RL frames (stock 'I' binary @ 25Hz) from {args.traj} ...")
            ser.write(b"kup\n")
            time.sleep(1.2)
            _ = ser.read(ser.in_waiting or 512)
            # Ensure stock gyroBalanceQ is OFF so self-righting ('rc') does not abort handstand
            ser.write(b"G~")
            time.sleep(0.25)
            g_reply = ser.read(ser.in_waiting or 256).decode(errors="replace")
            if "G" in g_reply and "g" not in g_reply:
                ser.write(b"G~")
                time.sleep(0.25)
                g_reply = ser.read(ser.in_waiting or 256).decode(errors="replace")
            print(f"[deploy] Gyro toggle state: {g_reply.strip()!r}")

            t0 = time.monotonic()
            for idx, row in enumerate(traj):
                target_t = t0 + idx * 0.04  # 25 Hz playback over stock serial
                payload = bytearray(b"I")
                for ch_offset, deg in enumerate(row):
                    val = max(-125, min(125, int(deg)))
                    payload.append(8 + ch_offset)
                    payload.append(val & 0xFF)
                payload.append(ord("~"))
                ser.write(payload)
                if ser.in_waiting:
                    _ = ser.read(ser.in_waiting)
                if idx % 10 == 0 or idx == len(traj) - 1:
                    print(f"\r[replay] frame {idx+1:3d}/{len(traj)} t={idx*0.04:4.2f}s ch8..15={row.tolist()}", end="", flush=True)
                dt = target_t - time.monotonic()
                if dt > 0:
                    time.sleep(dt)
            print()
            time.sleep(0.4)
            ser.write(b"kup\n")
            time.sleep(1.0)
            ser.write(b"d\n")
            time.sleep(0.3)
            tail_rx = ser.read(ser.in_waiting or 512).decode(errors="replace")
            print(f"[deploy] Replay complete, returned to stand & rested ('d'). tail_rx={tail_rx!r}")
            return

        if args.mode == "live":
            print("[deploy] Moving to RL starting stand pose (y0)...")
            ser.write(b"y0\n")
            time.sleep(0.8)
            ser.read(512)

        ser.reset_input_buffer()
        ser.write(b"y1\n")  # Start 50 Hz binary IMU stream (and disable stock self-righting gyro)
        rx_buf = bytearray()

        first = read_imu_packet(ser, rx_buf, timeout=2.0)
        if first is None:
            ser.write(b"yx\n")
            raise SystemExit("ERROR: No binary IMU packets (0xAA 0x55) received after sending 'y1'. Is RL bridge firmware flashed?")

        ang0, grav0 = imu_to_usd(*first)
        ang_hist = deque([ang0] * 4, maxlen=4)
        grav_hist = deque([grav0] * 4, maxlen=4)
        act_hist = deque([np.zeros(8, dtype=np.float32)] * 4, maxlen=4)

        steps = 0
        t_start = time.monotonic()
        fall_since = None
        last_print = 0.0
        reason = "completed"

        try:
            while time.monotonic() - t_start < args.duration:
                pkt = read_imu_packet(ser, rx_buf, timeout=0.25)
                if pkt is None:
                    continue
                # Drain queued packets to act on the freshest IMU sample
                while True:
                    idx = rx_buf.find(PKT_HEADER)
                    if idx >= 0 and len(rx_buf) - idx >= PKT_LEN:
                        del rx_buf[:idx]
                        vals = struct.unpack("<hhhhhh", bytes(rx_buf[2:PKT_LEN]))
                        del rx_buf[:PKT_LEN]
                        pkt = (vals[:3], vals[3:])
                    else:
                        break

                ang, grav = imu_to_usd(*pkt)
                ang_hist.append(ang)
                grav_hist.append(grav)

                if args.mode == "live" and args.catch:
                    # Roll > ~58 deg or flipped onto back -> catch on four paws
                    if abs(float(grav[0])) > 0.85 or float(grav[2]) > 0.75:
                        if fall_since is None:
                            fall_since = time.monotonic()
                        elif time.monotonic() - fall_since > 0.12:
                            reason = f"fall_catch g=({grav[0]:+.2f},{grav[1]:+.2f},{grav[2]:+.2f})"
                            break
                    else:
                        fall_since = None

                obs = np.concatenate([
                    np.concatenate(list(ang_hist)),
                    np.concatenate(list(grav_hist)),
                    np.concatenate(list(act_hist)),
                ]).astype(np.float32)
                act = infer(obs)
                act_hist.append(act)
                oc8 = action_to_opencat_8(act)

                if args.mode == "live":
                    ser.write(b"U" + struct.pack("8b", *oc8) + b"~")

                steps += 1
                now = time.monotonic()
                if now - last_print >= 0.1:
                    last_print = now
                    hz = steps / max(1e-3, now - t_start)
                    print(
                        f"\r[{args.mode}] t={now - t_start:4.1f}s ({hz:4.1f}Hz) "
                        f"g=({grav[0]:+.2f},{grav[1]:+.2f},{grav[2]:+.2f}) "
                        f"w=({ang[0]:+.2f},{ang[1]:+.2f},{ang[2]:+.2f}) "
                        f"ch8..15={oc8}",
                        end="",
                        flush=True,
                    )
        except KeyboardInterrupt:
            reason = "ctrl_c"
        finally:
            print()
            ser.write(b"yx\n")
            time.sleep(0.05)
            if args.mode == "live":
                ser.write(b"kbalance\n" if "fall_catch" in reason else b"ksit\n")
                time.sleep(0.8)
            else:
                ser.write(b"d\n")
            elapsed = time.monotonic() - t_start
            print(f"[deploy] Stopped ({reason}): {steps} steps in {elapsed:.2f}s ({steps/max(1e-3,elapsed):.1f} Hz avg)")


if __name__ == "__main__":
    main()
