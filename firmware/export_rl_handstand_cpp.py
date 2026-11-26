#!/usr/bin/env python3
"""Export Isaac Lab Bittle handstand checkpoint to ESP32 C++ headers and verify C++/PyTorch parity."""
import argparse
import os
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import torch


DEFAULT_CKPT = (
    "/home/robotics/isaac/IsaacLab/logs/rsl_rl/bittle_handstand_real/"
    "2026-11-25_16-33-26/model_2499.pt"
)
DEFAULT_OUT = Path(__file__).resolve().parent / "rlHandstandWeights.h"

# Matches Isaac Lab Articulation robot.joint_names order:
# ['left_back_shoulder_joint', 'left_back_knee_joint',
#  'left_front_shoulder_joint', 'left_front_knee_joint',
#  'right_back_shoulder_joint', 'right_back_knee_joint',
#  'right_front_shoulder_joint', 'right_front_knee_joint']
JOINT_NAMES = [
    "left_back_shoulder_joint",
    "left_back_knee_joint",
    "left_front_shoulder_joint",
    "left_front_knee_joint",
    "right_back_shoulder_joint",
    "right_back_knee_joint",
    "right_front_shoulder_joint",
    "right_front_knee_joint",
]
OPENCAT_INDICES = [11, 15, 8, 12, 10, 14, 9, 13]
OPENCAT_SIGNS = [1.0, 1.0, 1.0, 1.0, -1.0, -1.0, -1.0, -1.0]
DEFAULT_JOINT_POS_RAD = [0.0, 0.4, 0.0, 0.4, 0.0, -0.4, 0.0, -0.4]


def format_c_array(name: str, arr: np.ndarray, per_line: int = 8) -> str:
    flat = arr.astype(np.float32).reshape(-1)
    lines = [f"static const float {name}[{flat.size}] = {{"]
    for i in range(0, flat.size, per_line):
        chunk = ", ".join(f"{float(v):.8e}f" for v in flat[i : i + per_line])
        comma = "," if i + per_line < flat.size else ""
        lines.append(f"  {chunk}{comma}")
    lines.append("};")
    return "\n".join(lines)


def export_header(ckpt_path: Path, out_path: Path) -> dict[str, np.ndarray]:
    ckpt = torch.load(str(ckpt_path), map_location="cpu", weights_only=False)
    sd = ckpt["actor_state_dict"]

    arrays = {
        "RL_OBS_MEAN": sd["obs_normalizer._mean"].squeeze(0).cpu().numpy(),
        "RL_OBS_STD": (sd["obs_normalizer._std"] + 1.0e-2).squeeze(0).cpu().numpy(),
        "RL_W0": sd["mlp.0.weight"].cpu().numpy(),
        "RL_B0": sd["mlp.0.bias"].cpu().numpy(),
        "RL_W2": sd["mlp.2.weight"].cpu().numpy(),
        "RL_B2": sd["mlp.2.bias"].cpu().numpy(),
        "RL_W4": sd["mlp.4.weight"].cpu().numpy(),
        "RL_B4": sd["mlp.4.bias"].cpu().numpy(),
        "RL_W6": sd["mlp.6.weight"].cpu().numpy(),
        "RL_B6": sd["mlp.6.bias"].cpu().numpy(),
    }

    assert arrays["RL_OBS_MEAN"].shape == (56,)
    assert arrays["RL_OBS_STD"].shape == (56,)
    assert arrays["RL_W0"].shape == (256, 56)
    assert arrays["RL_W2"].shape == (128, 256)
    assert arrays["RL_W4"].shape == (64, 128)
    assert arrays["RL_W6"].shape == (8, 64)

    parts = [
        "// Auto-generated from Isaac Lab Bittle handstand checkpoint.",
        f"// Source: {ckpt_path}",
        "#pragma once",
        "#include <stdint.h>",
        "",
        "#define RL_OBS_DIM 56",
        "#define RL_ACT_DIM 8",
        "#define RL_HIST_LEN 4",
        "#define RL_H1 256",
        "#define RL_H2 128",
        "#define RL_H3 64",
        "#define RL_ACT_SCALE 0.4f",
        "#define RL_ACT_CLIP 4.0f",
        "#define RL_STEP_PERIOD_US 20000UL",
        "",
        "static const uint8_t RL_JOINT_OC_IDX[RL_ACT_DIM] = {11, 15, 8, 12, 10, 14, 9, 13};",
        "static const float RL_JOINT_OC_SIGN[RL_ACT_DIM] = {1.0f, 1.0f, 1.0f, 1.0f, -1.0f, -1.0f, -1.0f, -1.0f};",
        "static const float RL_DEFAULT_RAD[RL_ACT_DIM] = {0.0f, 0.4f, 0.0f, 0.4f, 0.0f, -0.4f, 0.0f, -0.4f};",
        "",
    ]
    for name, arr in arrays.items():
        parts.append(format_c_array(name, arr))
        parts.append("")

    out_path.write_text("\n".join(parts))
    print(f"Wrote {out_path} ({out_path.stat().st_size} bytes)")
    return arrays


def verify_cpp_parity(ckpt_path: Path, weights_header: Path) -> None:
    ckpt = torch.load(str(ckpt_path), map_location="cpu", weights_only=False)
    sd = ckpt["actor_state_dict"]
    mean = sd["obs_normalizer._mean"]
    std = sd["obs_normalizer._std"] + 1.0e-2
    w0, b0 = sd["mlp.0.weight"], sd["mlp.0.bias"]
    w2, b2 = sd["mlp.2.weight"], sd["mlp.2.bias"]
    w4, b4 = sd["mlp.4.weight"], sd["mlp.4.bias"]
    w6, b6 = sd["mlp.6.weight"], sd["mlp.6.bias"]
    elu = torch.nn.ELU()

    rng = np.random.default_rng(123)
    samples = rng.normal(0.0, 1.0, size=(16, 56)).astype(np.float32)
    samples[0, :] = 0.0
    samples[1, 12:24] = np.tile([0.0, 0.0, -1.0], 4)  # standing gravity history
    samples[2, 12:24] = np.tile([0.0, 1.0, 0.0], 4)   # handstand gravity history

    with torch.no_grad():
        tx = torch.from_numpy(samples)
        nx = (tx - mean) / std
        h1 = elu(nx @ w0.T + b0)
        h2 = elu(h1 @ w2.T + b2)
        h3 = elu(h2 @ w4.T + b4)
        ty = torch.clamp(h3 @ w6.T + b6, -4.0, 4.0).numpy()

    cpp_test = f"""
#include <cstdio>
#include <cmath>
#include "{weights_header.parent / 'rlHandstand.h'}"

int main() {{
  RlHandstandEngine eng;
  float obs[RL_OBS_DIM];
  float out[RL_ACT_DIM];
  for (int s = 0; s < 16; ++s) {{
    for (int i = 0; i < RL_OBS_DIM; ++i) {{
      if (scanf("%f", &obs[i]) != 1) return 1;
    }}
    eng.forwardRaw(obs, out);
    for (int j = 0; j < RL_ACT_DIM; ++j) {{
      printf("%.8e%c", out[j], j == RL_ACT_DIM - 1 ? '\\n' : ' ');
    }}
  }}
  return 0;
}}
"""
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "parity_test.cpp"
        exe = Path(td) / "parity_test"
        src.write_text(cpp_test)
        subprocess.run(["g++", "-O2", str(src), "-o", str(exe)], check=True)
        stdin_txt = "\n".join(" ".join(f"{float(v):.8e}" for v in row) for row in samples)
        res = subprocess.run([str(exe)], input=stdin_txt, text=True, capture_output=True, check=True)

    cy = np.array([[float(tok) for tok in line.split()] for line in res.stdout.strip().splitlines()], dtype=np.float32)
    max_diff = float(np.max(np.abs(ty - cy)))
    print(f"PyTorch vs C++ max_abs_diff across 16 samples: {max_diff:.3e}")
    assert max_diff < 1e-5, f"Parity mismatch: {max_diff}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", type=Path, default=Path(DEFAULT_CKPT))
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()

    export_header(args.checkpoint, args.out)
    if args.verify:
        verify_cpp_parity(args.checkpoint, args.out)


if __name__ == "__main__":
    main()
