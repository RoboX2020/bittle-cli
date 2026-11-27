# Lab 02: OpenCat Terminal Control, BLE Debugging & Motion Composition

## Learning Objectives
By the end of this lab, you will be able to:
1. Install and run `bittle-cli` across BLE, USB serial, Classic Bluetooth (`_SSP`), and WiFi WebSockets.
2. Debug real Linux/BlueZ BLE GATT issues (`0000ffe0/ffe1` vs Nordic `6e40`, paired devices, and 15 ms chunk pacing).
3. Compose multi-skill trajectories (`bittle_mix.py` & `combos.json`) and timed chains (`CHAINS`, `seq`, `--onboard`).
4. Verify custom commands safely without hardware using `mock_bittle.py` and `test_bittle.py`.

---

## 1. Installing `bittle-cli`

```bash
git clone https://github.com/RoboX2020/bittle-cli.git
cd bittle-cli
pip install -e .
```
This installs two global console commands (`pyproject.toml` / `setup.py`):
- `bittle` → `bittle_cli:main_cli`
- `bittle-mock` → `mock_bittle:main`

Core dependencies (`requirements.txt`): `pyserial>=3.5`, `bleak>=0.21.0`, `websockets>=11.0`.

---

## 2. Lab Exercise A: Zero-Hardware Verification (`mock_bittle.py`)

Run the automated 10-test suite first:
```bash
python3 test_bittle.py
```
This spins up `mock_bittle.py` with both a WebSocket server (`ws://127.0.0.1:8089`) and a virtual serial PTY (`/tmp/ttyBittle_test`) and verifies `10/10` passes across `list`, `scan`, `ksit`, `play flipShow` (`K` binary base64 + `gb`/`gB`), `chain moonwalkBow`, `chain partyTrick --onboard`, `stop`, and virtual serial `play boxerCombo`.

To test interactively in two terminals:
```bash
# Terminal 1
bittle-mock

# Terminal 2
bittle --wifi 127.0.0.1:8081
# or:
bittle --serial /tmp/ttyBittle
```

---

## 3. Case Study: Fixing Real Linux BLE Control (`PetoiBLE-4CB5`)

Initial attempts to run `bittle --ble` against our real Bittle (`PetoiBLE-4CB5`, `60:33:66:0A:4C:B5`) failed. Root causes and fixes implemented in `bittle_cli.py`:

1. **GATT Service UUID Mismatch:**
   - Original code hardcoded Nordic UART (`6e400001-...`).
   - Petoi Bittle X uses TI/Petoi UART (`0000ffe0-0000-1000-8000-00805f9b34fb`) with shared characteristic `0000ffe1-...`.
   - **Fix:** `BleLink.open` dynamically discovers `ffe1`, `6e400002`/`6e400003`, or any `write` + `notify` characteristics.
2. **Paired Devices Stop Advertising:**
   - Once paired in Ubuntu Bluetooth settings, Bittle stopped broadcasting BLE beacons, so `BleakScanner.discover()` returned nothing.
   - **Fix:** `find_ble` and `scan` inspect `get_global_bluez_manager()._properties` for `org.bluez.Device1` (`Connected` / `Paired`) before scanning advertisements.
3. **Boot Banner Race & BLE Buffer Overflow:**
   - Connecting over BLE triggers BiBoard boot (`Init IMU` → `Ready!`). Commands sent immediately were dropped, and `2 ms` chunk intervals dropped bytes on 149-byte `K` payloads.
   - **Fix:** Wait up to `4.5 s` for `"Ready!"` / `"Start"` + `0.5 s` settle, and pace 20-byte `CHUNK` writes at **`15 ms`** (`await asyncio.sleep(0.015)`).

---

## 4. Motion Fusion Engine (`bittle_mix.py` & `combos.json`)

`combos.json` ships 14 pre-compiled binary arrays (`flipShow`, `flipFlip`, `boxerCombo`, `partyDog`, `gymDog`, `detective`, `sleepyDog`, `stuntDog`, `pawsUp`, `playDeadRevive`, `fetchShow`, `trickShot`, `handstand`, `rearStand`).

### Binary Format & Rules
- Header: `[-num_frames, 0, 0, angle_ratio, loop_start, loop_end, loop_count]`
- Each frame: `16` `int8` joint angles (halved if `peak > 125°` with `angle_ratio = 2`) + `4` control bytes (`speed, delay_x50ms, gyro_trigger, 0`).
- **ESP32 Buffer Limit:** `ESP32_MAX_FRAMES = 125` (`BUFF_LEN = 2507 = 125*20 + 7`).
- **Seam Safety:** Jumps `> 60°` at segment boundaries automatically slow `entry_speed = 6` (unless a gyro trigger is set).
- **Gyro Guard:** Skills in `VIOLENT` (`bf`, `ff`, `flip`, `rl`, `hds`, `jmp`, `rc`, `handstand`, etc.) automatically wrap execution in `gb` → move → `gB`.

### Interactive Shell Commands
```text
bittle> list
bittle> play flipShow
bittle> chain partyTrick --onboard
bittle> seq customDemo ksit:1 khi:0.5 kwkF:2 kbalance:0
bittle> mix myStunt sit hi*2 bf chr zz@40     # needs --vault <Bittle_Knowledge_Vault>
```
*(Note: No `Bittle_Knowledge_Vault` folder is stored locally, so `combos.json` provides pre-compiled arrays; `seq` saves user chains to `my_combos.json` or `~/.config/bittle/my_combos.json`.)*

---

## Verification Checklist
- [ ] `python3 test_bittle.py` passes `10/10` tests
- [ ] `bittle scan` discovers paired BlueZ devices and serial ports
- [ ] `bittle --ble play flipShow` or `bittle --wifi 127.0.0.1:8081 play flipShow` confirms `g` → `k` → `g`
