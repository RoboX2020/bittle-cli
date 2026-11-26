#!/usr/bin/env python3
"""Terminal controller for Petoi Bittle X: connect over Bluetooth LE, WiFi or serial
(USB cable or paired classic-Bluetooth port) and run stock skills, fused combos and chains.

Protocol details come from the OpenCatEsp32 firmware in the Bittle vault:
  BLE   Nordic UART service 6E400001-..., write RX 6E400002, notify TX 6E400003 (bleCommon.h)
  WiFi  WebSocket ws://<ip>:81, JSON {"type":"command","taskId","commands":[...]},
        binary tokens sent as "b64:<token+bytes>" (webServer.h, PetoiWebCodingBlocks)
  Serial 115200 baud; lowercase tokens end with '\\n', uppercase (binary) tokens with '~';
        the robot echoes the token when a skill finishes (reaction.h)

Examples:
  python3 bittle_cli.py scan                         # find BLE robots and serial ports
  python3 bittle_cli.py --ble                        # connect to the first Bittle over BLE, open the shell
  python3 bittle_cli.py --wifi 192.168.1.42 play flipShow
  python3 bittle_cli.py --serial /dev/rfcomm0 chain victoryLap
  python3 bittle_cli.py --serial /dev/ttyUSB0 wifi-setup MyWifi MyPassword
"""
import argparse, asyncio, base64, json, shlex, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
NORDIC_UART_SERVICE = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
PETOI_UART_SERVICE = "0000ffe0-0000-1000-8000-00805f9b34fb"
UART_SERVICES = [NORDIC_UART_SERVICE, PETOI_UART_SERVICE, "ffe0"]
CHUNK = 20                                            # ardSerial slices writes into 20-byte packets

# Skills that can turn the robot upside down. With gyro balancing on, the firmware
# aborts them and runs rc (self-righting), so they run with balancing off ("gb" ... "gB").
VIOLENT = {"bf", "ff", "flip", "flipF", "flipD", "rl", "hds", "jmp", "rc", "handstand", "holdHDS", "kick"}

# Chains: [command, seconds to keep going after the robot confirms it].
CHAINS = {
    "victoryLap":  [["kwkF", 3], ["kup", 0.5], ["kbf", 1], ["kchr", 0]],
    "patrol":      [["ktrF", 2.5], ["kck", 0.5], ["ksnf", 0.5], ["kvtL", 1.5], ["ktrF", 2.5], ["kbalance", 0]],
    "moonwalkBow": [["kmw", 0.5], ["kstr", 1.5], ["kup", 0]],
    "zoomies":     [["kbdF", 2], ["kvtL", 1.5], ["kbdF", 1.5], ["krl", 0]],
    "sneakAttack": [["kcrF", 3], ["kup", 0.3], ["kjpF", 1.2], ["kbx", 0]],
    "gapRunner":   [["kgpF", 3], ["kphF", 2], ["khu", 0]],
    "guardDog":    [["kbalance", 0.5], ["kang", 0.5], ["kkc", 0.5], ["kbk", 2], ["ksit", 0]],
    "partyTrick":  [["ksit", 0.8], ["khi", 0.3], ["kfiv", 0.3], ["khsk", 0.3], ["kpee", 0]],
    "headBang":    [["ksit", 0.5], ["o 1 8, 0 0 30 4 0, 1 -30 30 4 30", 3], ["ksit", 0]],
    "fetch":       [["kwkArmF", 3], ["kpickF", 0.5], ["kbkArmF", 3], ["kputF", 0]],     # arm
    "basketball":  [["khunt", 0.5], ["kshowOff", 0.8], ["klaunch", 0]],                  # arm
}

def get_user_file():
    local_file = HERE / "my_combos.json"
    cwd_file = Path("my_combos.json")
    if local_file.exists():
        return local_file
    if cwd_file.exists():
        return cwd_file
    try:
        if os.access(HERE, os.W_OK):
            return local_file
    except Exception:
        pass
    config_dir = Path.home() / ".config" / "bittle"
    try:
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "my_combos.json"
    except Exception:
        return cwd_file

USER_FILE = get_user_file()


# ---------------------------------------------------------------- encoding

def is_binary(cmd):
    return isinstance(cmd, tuple)


def to_bytes(cmd):
    """Serial/BLE wire format. cmd is a text command or (TOKEN, [int8 values])."""
    if is_binary(cmd):
        token, values = cmd
        return token.encode() + bytes(v & 0xFF for v in values) + b"~"
    return cmd.encode() + b"\n"


def to_web(cmd):
    """WebSocket format: firmware re-adds the '~' terminator after base64 decoding."""
    if is_binary(cmd):
        token, values = cmd
        return "b64:" + base64.b64encode(token.encode() + bytes(v & 0xFF for v in values)).decode()
    return cmd


def token_of(cmd):
    return cmd[0] if is_binary(cmd) else cmd.lstrip()[0]


def skill_names(cmd):
    """Stock skill names a text command or a q-chain would run."""
    if is_binary(cmd):
        return set()
    if cmd.startswith("q"):
        return {p.split(":")[0][1:].strip() for p in cmd[1:].split(">") if p.startswith("k")}
    return {cmd[1:].strip()} if cmd.startswith("k") else set()


# ---------------------------------------------------------------- transports

class Transport:
    """Base for byte-stream links (serial, BLE). Robot output is printed and queued as lines."""
    def __init__(self, echo):
        self.lines = asyncio.Queue()
        self.buf = b""
        self.echo = echo
        self.listeners = []                           # called with every line (stand telemetry)

    def _feed(self, data):
        self.buf += data
        while b"\n" in self.buf:
            line, self.buf = self.buf.split(b"\n", 1)
            text = line.decode(errors="replace").strip()
            if text:
                for fn in self.listeners:
                    fn(text)
                if text.startswith("#B ") and text[3:4].isdigit():
                    continue                          # telemetry: only listeners get it
                if self.echo:
                    print(f"  \033[2mrobot> {text}\033[0m")
                self.lines.put_nowait(text)

    async def post(self, cmd):
        """Send without waiting for the echo (high-rate streams such as yu)."""
        data = to_bytes(cmd)
        for i in range(0, len(data), CHUNK):
            await self.write(data[i:i + CHUNK])

    async def send(self, cmd, timeout=10.0):
        """Send one command and wait until the robot echoes its token (or timeout)."""
        while not self.lines.empty():
            self.lines.get_nowait()
        data = to_bytes(cmd)
        for i in range(0, len(data), CHUNK):
            await self.write(data[i:i + CHUNK])
            await asyncio.sleep(0.015)
        want = token_of(cmd).lower()
        deadline = time.monotonic() + timeout
        while (left := deadline - time.monotonic()) > 0:
            try:
                line = await asyncio.wait_for(self.lines.get(), left)
            except asyncio.TimeoutError:
                break
            if line.lower() == want:
                return True
        return False


class SerialLink(Transport):
    def __init__(self, port, echo):
        super().__init__(echo)
        import serial
        self.ser = serial.Serial(port, 115200, timeout=0.1)
        self.loop = asyncio.get_running_loop()
        self.alive = True
        self.loop.run_in_executor(None, self._reader)

    def _reader(self):
        while self.alive:
            try:
                data = self.ser.read(256)
            except Exception:
                break
            if data:
                self.loop.call_soon_threadsafe(self._feed, data)

    async def write(self, data):
        self.ser.write(data)

    async def close(self):
        self.alive = False
        self.ser.close()


class BleLink(Transport):
    def __init__(self, echo):
        super().__init__(echo)
        self.rx_char = None
        self.tx_char = None

    @classmethod
    async def open(cls, target, echo):
        from bleak import BleakClient
        self = cls(echo)
        dev = await find_ble(target)
        if not dev:
            raise SystemExit("No Bittle found over BLE. Is it on, and not connected to the phone app?")
        print(f"connecting to {dev.name} ({dev.address}) ...")
        self.client = BleakClient(dev)
        await self.client.connect()

        # Dynamically discover RX and TX characteristics (supports Petoi FFE1 and Nordic NUS)
        for s in self.client.services:
            for c in s.characteristics:
                uuid = c.uuid.lower()
                if "ffe1" in uuid:
                    self.rx_char = c.uuid
                    self.tx_char = c.uuid
                    break
                if "6e400002" in uuid:
                    self.rx_char = c.uuid
                elif "6e400003" in uuid:
                    self.tx_char = c.uuid
            if self.rx_char and self.tx_char:
                break

        if not self.rx_char or not self.tx_char:
            for s in self.client.services:
                for c in s.characteristics:
                    if not self.rx_char and ("write" in c.properties or "write-without-response" in c.properties):
                        self.rx_char = c.uuid
                    if not self.tx_char and "notify" in c.properties:
                        self.tx_char = c.uuid

        if not self.rx_char or not self.tx_char:
            raise SystemExit("Could not find suitable UART characteristic on BLE device")

        await self.client.start_notify(self.tx_char, lambda _, data: self._feed(bytes(data)))
        # Wait for robot boot banner and initialization to complete
        ready_evt = asyncio.Event()
        def on_boot_line(text):
            if "Ready!" in text or "Start" in text:
                ready_evt.set()
        self.listeners.append(on_boot_line)
        try:
            await asyncio.wait_for(ready_evt.wait(), timeout=4.5)
        except asyncio.TimeoutError:
            pass
        finally:
            if on_boot_line in self.listeners:
                self.listeners.remove(on_boot_line)
        await asyncio.sleep(0.5)
        while not self.lines.empty():
            self.lines.get_nowait()
        return self

    async def write(self, data):
        await self.client.write_gatt_char(self.rx_char, data, response=False)

    async def close(self):
        await self.client.disconnect()


class WifiLink:
    @classmethod
    async def open(cls, host, echo):
        import websockets
        self = cls()
        self.echo = echo
        if host.startswith("ws://") or host.startswith("wss://"):
            url = host
        elif ":" in host:
            url = f"ws://{host}"
        else:
            url = f"ws://{host}:81"
        self.ws = await websockets.connect(url, max_size=None)
        self.pending = {}
        self.reader = asyncio.create_task(self._read())
        self.beat = asyncio.create_task(self._heartbeat())
        return self

    async def _read(self):
        async for raw in self.ws:
            try:
                msg = json.loads(raw)
            except ValueError:
                continue
            if msg.get("type") == "response" and msg.get("status") in ("completed", "error"):
                for r in msg.get("results", []):
                    for line in str(r).splitlines():
                        if line.strip() and self.echo:
                            print(f"  \033[2mrobot> {line.strip()}\033[0m")
                fut = self.pending.pop(msg.get("taskId"), None)
                if fut and not fut.done():
                    fut.set_result(msg["status"] == "completed")
            elif msg.get("type") == "error":
                print(f"  robot error: {msg.get('error')}")

    async def _heartbeat(self):
        while True:                                   # firmware drops clients after 40 s of silence
            await asyncio.sleep(15)
            await self.ws.send(json.dumps({"type": "heartbeat", "timestamp": int(time.time() * 1000)}))

    async def send(self, cmd, timeout=10.0):
        task_id = str(int(time.time() * 1000))
        fut = asyncio.get_running_loop().create_future()
        self.pending[task_id] = fut
        await self.ws.send(json.dumps({"type": "command", "taskId": task_id,
                                       "commands": [to_web(cmd)], "timestamp": int(time.time() * 1000)}))
        try:
            return await asyncio.wait_for(fut, timeout)
        except asyncio.TimeoutError:
            self.pending.pop(task_id, None)
            return False

    async def close(self):
        self.beat.cancel()
        self.reader.cancel()
        await self.ws.close()


async def find_ble(target=None, timeout=6.0):
    from bleak.backends.device import BLEDevice

    # 1. Check BlueZ manager for already connected or paired devices
    try:
        from bleak.backends.bluezdbus.manager import get_global_bluez_manager
        manager = await get_global_bluez_manager()
        connected_devs = []
        known_devs = []
        for path, p in manager._properties.items():
            if "org.bluez.Device1" in p:
                props = p["org.bluez.Device1"]
                addr = props.get("Address", "")
                name = props.get("Name", "") or props.get("Alias", "")
                uuids = [u.lower() for u in props.get("UUIDs", [])]
                is_ble = any("ffe0" in u or "6e40" in u for u in uuids) or "ble" in name.lower() or name.endswith("_BLE")
                if target:
                    if target.lower() in name.lower() or target.lower() in addr.lower():
                        return BLEDevice(addr, name, details={"path": path, "props": props})
                elif is_ble or "bittle" in name.lower() or "petoi" in name.lower():
                    # Skip classic Bluetooth only device if it lacks BLE
                    if not is_ble and any("1101" in u for u in uuids):
                        continue
                    dev = BLEDevice(addr, name, details={"path": path, "props": props})
                    if props.get("Connected"):
                        connected_devs.append(dev)
                    else:
                        known_devs.append(dev)
        if connected_devs:
            return connected_devs[0]
        if known_devs:
            return known_devs[0]
    except Exception:
        pass

    # 2. Discover devices actively broadcasting advertisements
    try:
        from bleak import BleakScanner
        found = await BleakScanner.discover(timeout=timeout, return_adv=True)
        robots = []
        fallback_robots = []
        for dev, adv in found.values():
            name = dev.name or adv.local_name or ""
            adv_uuids = [u.lower() for u in adv.service_uuids]
            uart = any(s in u for s in ["ffe0", "6e40"] for u in adv_uuids)
            if target:
                if target.lower() in name.lower() or target.lower() in dev.address.lower():
                    robots.append(dev)
            elif "bittle" in name.lower() or "petoi" in name.lower():
                robots.append(dev)
            elif uart or name.endswith("_BLE") or "ble" in name.lower():
                fallback_robots.append(dev)
        if robots:
            return robots[0]
        return fallback_robots[0] if fallback_robots else None
    except Exception as e:
        print(f"Bluetooth error: {e}")
        return None


# ---------------------------------------------------------------- library of moves

class Library:
    def __init__(self, combos_path, vault):
        self.vault = vault
        self.combos = {}
        self.segments = {}
        c_path = Path(combos_path) if combos_path else (HERE / "combos.json")
        if not c_path.exists():
            search_candidates = [
                Path("combos.json"),
                HERE / "combos.json",
                Path(__file__).resolve().parent / "combos.json",
                Path.home() / "bittle-cli" / "combos.json",
                Path.home() / ".local" / "share" / "bittle" / "combos.json",
                Path.home() / ".config" / "bittle" / "combos.json",
            ]
            for candidate in search_candidates:
                if candidate.exists():
                    c_path = candidate
                    break
        if c_path.exists():
            try:
                data = json.loads(c_path.read_text())
                self.combos = {k: v["array"] for k, v in data.items() if isinstance(v, dict) and "array" in v}
                self.segments = {k: v.get("segments", []) for k, v in data.items() if isinstance(v, dict)}
            except Exception as e:
                print(f"Warning: could not parse {c_path}: {e}")
        self.chains = dict(CHAINS)
        self.user = json.loads(USER_FILE.read_text()) if USER_FILE.exists() else {"combos": {}, "chains": {}}
        self.combos.update({k: v["array"] for k, v in self.user.get("combos", {}).items() if isinstance(v, dict) and "array" in v})
        self.chains.update(self.user.get("chains", {}))
        self.segments.update({k: v.get("segments", []) for k, v in self.user.get("combos", {}).items() if isinstance(v, dict)})

    def mix(self, name, segments):
        if not self.vault:
            raise ValueError("mix needs the vault: start with --vault <Bittle_Knowledge_Vault>")
        sys.path.insert(0, str(HERE))
        import bittle_mix
        arr, seams = bittle_mix.compose(self.vault, "Bittle X", segments)
        self.combos[name], self.segments[name] = arr, segments
        self.user["combos"][name] = {"segments": segments, "array": arr}
        USER_FILE.write_text(json.dumps(self.user, indent=1))
        return arr, seams

    def define_chain(self, name, steps):
        self.chains[name] = steps
        self.user["chains"][name] = steps
        USER_FILE.write_text(json.dumps(self.user, indent=1))


# ---------------------------------------------------------------- runner

class Runner:
    def __init__(self, link, lib, keep_gyro=False):
        self.link, self.lib, self.keep_gyro = link, lib, keep_gyro

    async def raw(self, cmd, timeout=10.0):
        ok = await self.link.send(cmd, timeout)
        if not ok:
            print(f"  (no confirmation for {cmd if isinstance(cmd, str) else cmd[0]!r} - it may still have run)")
        return ok

    async def guarded(self, names, coro):
        if self.keep_gyro or not (names & VIOLENT):
            return await coro
        print("  gyro balancing off for this move (stops auto-recover from cutting it short)")
        await self.link.send("gb", 2)
        try:
            return await coro
        finally:
            await self.link.send("gB", 2)

    async def combo(self, name):
        arr = self.lib.combos[name]
        segs = self.lib.segments.get(name, [])
        names = {s.split("*")[0].split("~")[0].split("@")[0] for s in segs}
        frames = -arr[0]
        print(f"> {name}: {' -> '.join(segs)}  ({frames} frames)")
        return await self.guarded(names, self.raw(("K", arr), timeout=5 + frames * 0.5))

    async def chain(self, name, onboard=False):
        steps = self.lib.chains[name]
        names = set().union(*(skill_names(c) for c, _ in steps))
        if onboard:                                   # one q string, the robot sequences it
            q = "q" + "".join(f"{c}:{int(s * 1000)}>" for c, s in steps)
            print(f"> {name} (on-board): {q}")
            total = sum(s for _, s in steps) + 6 * len(steps)
            return await self.guarded(names, self.raw(q, timeout=total))

        # Step by step: gyro off only around the violent steps, since fast gaits
        # such as trot are less stable with balancing off (Petoi remote docs).
        for cmd, secs in steps:
            print(f"> {cmd}" + (f"  then {secs}s" if secs else ""))
            await self.guarded(skill_names(cmd), self.raw(cmd, timeout=15))
            await asyncio.sleep(secs)

    async def play(self, name, onboard=False):
        if name in self.lib.combos:
            return await self.combo(name)
        if name in self.lib.chains:
            return await self.chain(name, onboard)
        return await self.guarded({name}, self.raw("k" + name, timeout=15))


# ---------------------------------------------------------------- two-leg stands (patched firmware)

STAND_HELP = """\
  needs the balance_stand firmware patch (token 'y'); see README "Handstand and rear stand"
  stand hand | rear         go up into a handstand / onto the hind legs, then hold
  stand here                hold whatever two-leg pose the robot is in now
  stand zero                setpoint = current tilt (hold it balanced, paws flat, then send)
  stand pose IDX DEG        trim one joint of the top pose (remembered for the next stand)
  stand gains KP KI KD      onboard PID (default 0 0 0 = hold the pose and catch falls)
  stand sign +1|-1 / stand mix M / stand limit LIM FALL / stand catch 0|1
  stand watch SECS [FILE]   live tilt display; FILE saves a CSV
  stand laptop KP KI KD SECS   run the PID on this computer instead (USB or BLE)
  stand rl-pose             move smoothly to the RL standing pose (y0)
  stand rl-dry [N]          dry-run onboard 50 Hz RL telemetry without moving servos (yS)
  stand rl [N]              run onboard 50 Hz RL handstand policy on BiBoard (yR)
  stand show / stand stop"""


class Telemetry:
    """Collects '#B ms pitch err u roll' lines."""
    def __init__(self, link, csv_path=None):
        self.link, self.rows, self.latest = link, [], None
        self.csv = open(csv_path, "w") if csv_path else None
        if self.csv:
            self.csv.write("ms,pitch,err,u,roll\n")
        self.events = []

    def __call__(self, text):
        if text.startswith("#RL "):
            print(f"  {text}")
            return
        if not text.startswith("#B "):
            return
        parts = text.split()
        if len(parts) == 6 and parts[1].isdigit():
            row = [float(x) for x in parts[1:]]
            self.latest = row
            self.rows.append(row)
            if self.csv:
                self.csv.write(",".join(parts[1:]) + "\n")
        else:
            self.events.append(text[3:])
            print(f"  stand: {text[3:]}")

    def __enter__(self):
        self.link.listeners.append(self)
        return self

    def __exit__(self, *exc):
        self.link.listeners.remove(self)
        if self.csv:
            self.csv.close()


def gauge(err, u, width=41, span=20.0):
    """One-line picture of the tilt error (|) and correction (*), +/- span degrees."""
    mid = width // 2
    line = [" "] * width
    line[mid] = "."
    for val, ch in ((u, "*"), (err, "|")):
        line[max(0, min(width - 1, mid + round(val / span * mid)))] = ch
    return "".join(line)


async def stand_watch(runner, secs, csv_path=None):
    link = runner.link
    if isinstance(link, WifiLink):
        print("  live telemetry needs USB serial or BLE (WiFi only returns output when a command ends)")
        return
    with Telemetry(link, csv_path) as tel:
        await runner.raw("yt 4", 3)                   # every 4th tick, ~50 Hz
        end = time.monotonic() + secs
        try:
            while time.monotonic() < end and "stop" not in " ".join(tel.events):
                await asyncio.sleep(0.1)
                if tel.latest:
                    ms, pitch, err, u, roll = tel.latest
                    print(f"\r  pitch {pitch:7.2f}  err {err:6.2f}  u {u:6.2f}  roll {roll:6.2f}  "
                          f"[{gauge(err, u)}]", end="", flush=True)
        finally:
            print()
            await runner.raw("yt 0", 3)
    if tel.rows:
        errs = [r[2] for r in tel.rows]
        rms = (sum(e * e for e in errs) / len(errs)) ** 0.5
        print(f"  {len(tel.rows)} samples, rms error {rms:.2f}°, max |u| {max(abs(r[3]) for r in tel.rows):.1f}°"
              + (f", saved {csv_path}" if csv_path else ""))


async def stand_laptop(runner, kp, ki, kd, secs, sign=1.0, limit=30.0):
    """PID on this computer: the robot streams tilt, we send the correction back with yu."""
    link = runner.link
    if isinstance(link, WifiLink):
        print("  laptop control needs USB serial or BLE; over WiFi the delay is too long to hold a stand")
        return
    if isinstance(link, BleLink):
        print("  note: BLE adds ~50-80 ms of delay; the simulation says this roughly halves the shove the stand survives")
    state = dict(integ=0.0, prev=None, dfilt=0.0, t=None)
    pending = asyncio.Queue()

    def on_row(text):
        if text.startswith("#B ") and text[3:4].isdigit():
            pending.put_nowait([float(x) for x in text.split()[1:]])

    link.listeners.append(on_row)
    sent = 0
    try:
        await runner.raw("ye 1", 3)
        await runner.raw("yt 2", 3)                   # ~100 Hz telemetry
        end = time.monotonic() + secs
        while time.monotonic() < end:
            try:
                ms, pitch, err, _, roll = await asyncio.wait_for(pending.get(), 0.5)
            except asyncio.TimeoutError:
                print("  no telemetry: is the robot standing (stand hand / rear / here)?")
                break
            while not pending.empty():                # always act on the newest sample
                ms, pitch, err, _, roll = pending.get_nowait()
            dt = 0.01 if state["t"] is None else max(1e-3, (ms - state["t"]) / 1000)
            state["t"] = ms
            d = 0.0 if state["prev"] is None else (err - state["prev"]) / dt
            state["prev"] = err
            state["dfilt"] += 0.35 * (d - state["dfilt"])
            pd = kp * err + kd * state["dfilt"]
            nxt = state["integ"] + err * dt
            if abs(pd + ki * nxt) < limit:
                state["integ"] = nxt
            u = max(-limit, min(limit, sign * (pd + ki * state["integ"])))
            await link.post(f"yu {u:.2f}")
            sent += 1
            if sent % 10 == 0:
                print(f"\r  err {err:6.2f}  u {u:6.2f}  [{gauge(err, u)}]", end="", flush=True)
    finally:
        print()
        link.listeners.remove(on_row)
        await runner.raw("yt 0", 3)
        await runner.raw("ye 0", 3)
    print(f"  sent {sent} corrections")


async def stand(runner, args):
    sub, rest = (args[0], args[1:]) if args else ("help", [])
    simple = {"hand": "yh", "rear": "yr", "here": "yg", "stop": "yx", "zero": "yz", "show": "y?",
              "rl-pose": "y0", "rl-dry": "yS", "rl": "yR"}
    with_args = {"pose": "yb", "gains": "yp", "sign": "ys", "mix": "ym", "limit": "yl", "catch": "yc"}
    if sub in simple:
        if sub in ("hand", "rear", "rl"):
            print("  going up... (any other command, or a fall, ends the stand)")
        cmd_str = simple[sub] + (f" {rest[0]}" if sub in ("rl", "rl-dry") and rest else "")
        tel = Telemetry(runner.link)
        if hasattr(runner.link, "listeners"):
            runner.link.listeners.append(tel)
        try:
            await runner.raw(cmd_str, timeout=20)
        finally:
            if hasattr(runner.link, "listeners"):
                runner.link.listeners.remove(tel)
    elif sub in with_args and rest:
        await runner.raw(with_args[sub] + " " + " ".join(rest), 3)
    elif sub == "watch":
        await stand_watch(runner, float(rest[0]) if rest else 10, rest[1] if len(rest) > 1 else None)
    elif sub == "laptop" and len(rest) >= 3:
        await stand_laptop(runner, *(float(x) for x in rest[:3]), secs=float(rest[3]) if len(rest) > 3 else 10)
    else:
        print(STAND_HELP)


HELP = """\
  list                      combos (fused skills) and chains (sequences)
  play NAME                 run a combo, a chain, or a stock skill (play hi)
  chain NAME [--onboard]    run a chain step by step, or as one robot-side q queue
  mix NAME seg seg ...      fuse skills into a new combo, save it, and play it
                            segments: hi  hi*2 (repeat)  sit~4 (slower)  zz@40 (hold 2 s)
  seq NAME cmd:sec ...      define a chain, e.g.  seq hello ksit:1 khi:0.5 kwkF:2
  gyro on|off               gyro balancing (off = no auto-recover)
  stand ...                 handstand / rear stand and tuning (type 'stand' for the list)
  stop                      rest and relax the servos (d)
  ksit / m0 30 / q...       anything else is sent to the robot as a raw command
  help, quit"""


async def handle(runner, line):
    lib = runner.lib
    try:
        parts = shlex.split(line)
    except ValueError as e:
        print(f"  {e}")
        return True
    if not parts:
        return True
    cmd, args = parts[0], parts[1:]
    if cmd in ("quit", "exit"):
        return False
    if cmd == "help":
        print(HELP)
    elif cmd == "list":
        print("combos (one uploaded skill):")
        for n in sorted(lib.combos):
            print(f"  {n:16s} {' -> '.join(lib.segments.get(n, []))}")
        print("chains (sequence of commands):")
        for n, steps in sorted(lib.chains.items()):
            print(f"  {n:16s} {' -> '.join(c for c, _ in steps)}")
    elif cmd == "play" and args:
        await runner.play(args[0], "--onboard" in args)
    elif cmd == "chain" and args:
        if args[0] not in lib.chains:
            print(f"  no chain {args[0]!r}")
        else:
            await runner.chain(args[0], "--onboard" in args)
    elif cmd == "mix" and len(args) >= 2:
        try:
            arr, seams = lib.mix(args[0], args[1:])
        except (ValueError, FileNotFoundError, SystemExit) as e:
            print(f"  {e}")
            return True
        big = {k: v for k, v in seams if v > 60}
        print(f"  saved {args[0]}: {-arr[0]} frames" + (f", slowed big seams {big}" if big else ""))
        await runner.combo(args[0])
    elif cmd == "seq" and len(args) >= 2:
        try:
            steps = [[c, float(s)] for c, s in (a.rsplit(":", 1) for a in args[1:])]
        except ValueError:
            print("  format: seq NAME cmd:seconds cmd:seconds ...")
            return True
        lib.define_chain(args[0], steps)
        print(f"  saved chain {args[0]}")
    elif cmd == "gyro" and args and args[0] in ("on", "off"):
        await runner.raw("gB" if args[0] == "on" else "gb", 3)
    elif cmd == "stop":
        await runner.raw("d", 5)
    elif cmd == "stand":
        await stand(runner, args)
    elif cmd in ("play", "chain", "mix", "seq", "gyro", "stand"):
        print(HELP)
    else:
        await runner.raw(line.strip(), timeout=15)
    return True


async def shell(runner):
    try:
        import readline
        words = ["list", "play", "chain", "mix", "seq", "gyro", "stand", "stop", "help", "quit"]
        readline.set_completer(lambda text, i: ([w for w in words + sorted(runner.lib.combos)
                                                 + sorted(runner.lib.chains) if w.startswith(text)] + [None])[i])
        readline.parse_and_bind("tab: complete")
    except ImportError:
        pass
    print("connected. type 'help' or 'list'.")
    loop = asyncio.get_running_loop()
    while True:
        try:
            line = await loop.run_in_executor(None, input, "bittle> ")
        except (EOFError, KeyboardInterrupt):
            break
        if not await handle(runner, line):
            break


async def scan():
    try:
        from bleak.backends.bluezdbus.manager import get_global_bluez_manager
        manager = await get_global_bluez_manager()
        print("BLE (paired / system connected):")
        has_bluez = False
        for path, p in manager._properties.items():
            if "org.bluez.Device1" in p:
                props = p["org.bluez.Device1"]
                addr = props.get("Address", "")
                name = props.get("Name", "") or props.get("Alias", "")
                uuids = [u.lower() for u in props.get("UUIDs", [])]
                is_ble = any("ffe0" in u or "6e40" in u for u in uuids) or "ble" in name.lower() or name.endswith("_BLE")
                if is_ble or "petoi" in name.lower() or "bittle" in name.lower():
                    conn_state = " [Connected]" if props.get("Connected") else " [Paired]"
                    print(f"  {name:24s} {addr}{conn_state}")
                    has_bluez = True
        if not has_bluez:
            print("  (none)")
    except Exception:
        pass

    try:
        from bleak import BleakScanner
        print("BLE (nearby advertisements):")
        found = await BleakScanner.discover(timeout=5, return_adv=True)
        count = 0
        for dev, adv in found.values():
            name = dev.name or adv.local_name or "?"
            adv_uuids = [u.lower() for u in adv.service_uuids]
            uart = any(s in u for s in ["ffe0", "6e40"] for u in adv_uuids)
            if uart or name.endswith("_BLE") or "ble" in name.lower() or "bittle" in name.lower() or "petoi" in name.lower():
                print(f"  {name:24s} {dev.address}")
                count += 1
        if count == 0:
            print("  (no additional advertising devices found)")
    except ImportError:
        print("BLE: install bleak to scan (pip install bleak)")
    except Exception as e:
        print(f"  (Bluetooth unavailable: {e})")
    try:
        from serial.tools import list_ports
        print("serial ports (USB, or paired classic Bluetooth '_SSP'):")
        for p in list_ports.comports():
            print(f"  {p.device:24s} {p.description}")
    except ImportError:
        print("serial: install pyserial to list ports (pip install pyserial)")


async def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    link = ap.add_mutually_exclusive_group()
    link.add_argument("--ble", nargs="?", const="", metavar="NAME_OR_ADDR", help="Bluetooth LE (default: first Bittle found)")
    link.add_argument("--wifi", metavar="IP", help="robot IP on your network (WebSocket port 81)")
    link.add_argument("--serial", metavar="PORT", help="USB or paired classic-Bluetooth serial port")
    ap.add_argument("--combos", default=str(HERE / "combos.json"))
    ap.add_argument("--vault", help="Bittle_Knowledge_Vault folder, needed for 'mix'")
    ap.add_argument("--keep-gyro", action="store_true", help="don't switch gyro balancing off for flips")
    ap.add_argument("--quiet", action="store_true", help="hide robot output")
    ap.add_argument("command", nargs=argparse.REMAINDER,
                    help="scan | wifi-setup SSID PASSWORD | any shell command (play flipShow); none = interactive")
    a = ap.parse_args()

    known_cmds = {"play", "chain", "mix", "seq", "gyro", "stop", "list", "scan", "help", "stand"}
    if a.ble and (a.ble in known_cmds or (len(a.ble) != 17 and (a.ble.startswith(("k", "m", "d", "g", "b", "q", "o")) or not any(x in a.ble.lower() for x in ("bittle", "petoi", ":"))))):
        a.command = [a.ble] + a.command
        a.ble = ""

    if a.command[:1] == ["scan"]:
        return await scan()
    if a.command[:1] == ["list"]:
        lib = Library(a.combos, a.vault)
        print("combos (fused skills):")
        for n in sorted(lib.combos):
            print(f"  {n:16s} {' -> '.join(lib.segments.get(n, []))}")
        print("chains (sequence of commands):")
        for n, steps in sorted(lib.chains.items()):
            print(f"  {n:16s} {' -> '.join(c for c, _ in steps)}")
        return
    echo = not a.quiet
    if a.ble is not None:
        conn = await BleLink.open(a.ble or None, echo)
    elif a.wifi:
        conn = await WifiLink.open(a.wifi, echo)
    elif a.serial:
        conn = SerialLink(a.serial, echo)
        await asyncio.sleep(0.5)
    else:
        ap.error("pick a link: --ble, --wifi IP or --serial PORT (try: scan)")

    runner = Runner(conn, Library(a.combos, a.vault), a.keep_gyro)
    try:
        if a.command[:1] == ["wifi-setup"]:
            if len(a.command) != 3 or a.wifi:
                ap.error("wifi-setup SSID PASSWORD, over --serial or --ble")
            print("sending WiFi credentials; the robot reboots and prints its IP when connected")
            await runner.raw(f"w%{a.command[1]}%{a.command[2]}", timeout=20)
            await asyncio.sleep(8)
        elif a.command:
            await handle(runner, shlex.join(a.command))
        else:
            await shell(runner)
    finally:
        await conn.close()


def main_cli():
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main_cli()
