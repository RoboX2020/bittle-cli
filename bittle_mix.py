#!/usr/bin/env python3
"""Mix-and-match Bittle X skills into new behavior arrays.

Reads the stored arrays from the vault's Actions/ notes, decodes them by the
signed period (posture = 1, gait > 1, behavior < 0), and splices postures and
behaviors into a new behavior that can be uploaded with the 'K' token
(Python API: ['K', array, seconds]).

Gaits are NOT spliced: they are cyclic 8-value frames with no speed/delay
fields, so they are chained with the task queue instead (see COMBOS.md).

Usage:
  python3 bittle_mix.py --vault <Bittle_Knowledge_Vault> [--model "Bittle X"] [--out combos.json]
"""
import argparse, json, re
from pathlib import Path

ESP32_MAX_FRAMES = 125   # OpenCat.h: BUFF_LEN 2507 = 125*20 + 7


def load_skill(vault, model, name):
    text = (Path(vault) / "Actions" / f"{model} - {name}.md").read_text()
    raw = json.loads(re.search(r"## Raw signed values\s*```json\s*(\[.*?\])", text, re.S).group(1))
    return raw


def decode(raw):
    """Return (kind, frames, loop) with frames as [16 angles in real degrees + 4 control]."""
    period, ratio = raw[0], raw[3]
    if period == 1:                                   # posture: 4 header + 16 angles
        angles = [a * ratio for a in raw[4:20]]
        return "posture", [angles + [8, 0, 0, 0]], None
    if period > 1:
        return "gait", None, None
    n = -period                                       # behavior: 7 header + n*20
    loop = tuple(raw[4:7])
    frames = []
    for i in range(n):
        f = raw[7 + 20 * i: 7 + 20 * (i + 1)]
        frames.append([a * ratio for a in f[:16]] + list(f[16:]))
    return "behavior", frames, loop


def unroll(frames, loop):
    """Expand the behavior's own loop so it survives being embedded in a bigger array."""
    start, end, count = loop
    if count <= 1 or end <= start:
        return [list(f) for f in frames]
    body = frames[start:end + 1]
    return [list(f) for f in frames[:start] + body * count + frames[end + 1:]]


def segment(vault, model, spec):
    """spec: 'name' | 'name*N' (repeat whole skill) | 'name~S' (cap speed of all frames at S)
    | 'name@D' (append D*50 ms hold on its last frame). Modifiers combine: 'hi*2~6@10'."""
    m = re.fullmatch(r"([A-Za-z0-9]+)(?:\*(\d+))?(?:~(\d+))?(?:@(\d+))?", spec)
    name, rep, cap, hold = m.group(1), int(m.group(2) or 1), m.group(3), m.group(4)
    kind, frames, loop = decode(load_skill(vault, model, name))
    if kind == "gait":
        raise SystemExit(f"{name} is a gait; chain it with the task queue, not inside a behavior")
    frames = unroll(frames, loop) if loop else frames
    frames = [list(f) for f in frames] * rep
    if cap:
        for f in frames:
            f[16] = int(cap) if f[16] == 0 else min(f[16], int(cap))
    if hold:
        frames[-1][17] = max(frames[-1][17], int(hold))
    return frames


def max_joint_jump(a, b):
    return max(abs(x - y) for x, y in zip(a[:16], b[:16]))


def compose(vault, model, specs, entry_speed=6, loop=(0, 0, 0)):
    frames, seams = [], []
    for spec in specs:
        seg = segment(vault, model, spec)
        if frames:
            jump = max_joint_jump(frames[-1], seg[0])
            seams.append((spec, jump))
            # Large pose change at a seam: slow the first frame of the new segment down,
            # unless that frame carries a gyro trigger (flip/jump timing must stay intact).
            if jump > 60 and seg[0][18] == 0 and (seg[0][16] == 0 or seg[0][16] > entry_speed):
                seg[0][16] = entry_speed
        frames += seg
    if len(frames) > ESP32_MAX_FRAMES:
        raise SystemExit(f"{len(frames)} frames > {ESP32_MAX_FRAMES} (ESP32 upload buffer)")
    peak = max(abs(a) for f in frames for a in f[:16])
    ratio = 1 if peak <= 125 else 2                    # signed bytes; ardSerial halves above 125
    out = [-len(frames), 0, 0, ratio, *loop]
    for f in frames:
        out += [round(a / ratio) for a in f[:16]] + f[16:]
    return out, seams


# Each combo: name, segments, optional loop (start, end, count) over the NEW frame indexes.
COMBOS = {
    # Most behaviors start and end in the neutral stand (legs at 30), so they chain cleanly.
    # rc is the self-righting move (starts on the back; firmware auto-runs it when flipped
    # with the gyro on): only use it after a fall, never after a landed flip.
    "flipShow":   ["sit", "hi", "bf", "chr"],                   # wave, backflip, cheer
    "flipFlip":   ["ff", "up@10", "bf", "gdb"],                 # front flip, settle 0.5 s, backflip
    "boxerCombo": ["up", "bx", "kc", "ang", "up"],              # box, kick, angry face
    "partyDog":   ["sit", "chr", "fiv", "hsk", "hg"],           # cheers, high-five, shake, hug
    "gymDog":     ["up", "pu", "pu1", "str", "rest"],           # push-ups, one-hand push-ups, stretch
    "detective":  ["up", "snf", "ck", "dg", "snf", "nd"],       # sniff, look around, dig, nod
    "sleepyDog":  ["str", "scrh", "sit~4", "zz@40"],            # stretch, scratch, slow sit, nap
    "stuntDog":   ["hds", "rl", "jmp", "up"],                   # handstand, roll, jump, stand
    "pawsUp":     ["sit", "hu", "wh", "fiv", "hi"],             # hands up, wave head, high-five, hi
    "playDeadRevive": ["pd", "str", "chr"],                     # play dead (gets up itself), stretch, cheer
    # arm-only (Bittle X with the robotic arm)
    "fetchShow":  ["pickF", "showOff", "putF", "clap"],
    "trickShot":  ["hunt", "showOff", "tossF", "clap"],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", required=True)
    ap.add_argument("--model", default="Bittle X")
    ap.add_argument("--out", default="combos.json")
    args = ap.parse_args()
    result = {}
    for name, specs in COMBOS.items():
        arr, seams = compose(args.vault, args.model, specs)
        result[name] = {"segments": specs, "frames": -arr[0], "angle_ratio": arr[3],
                        "seam_max_joint_jump_deg": dict(seams), "array": arr}
        print(f"{name:16s} {-arr[0]:3d} frames  ratio {arr[3]}  seams {dict(seams)}")
    Path(args.out).write_text(json.dumps(result, indent=1))
    print("wrote", args.out)


if __name__ == "__main__":
    main()
