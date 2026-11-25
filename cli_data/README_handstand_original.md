# Bittle X terminal controller

```bash
pip install pyserial bleak websockets
```

Keep all files in one folder: `bittle_cli.py`, `bittle_mix.py` and `combos.json`.

## 1. Find the dog
```bash
python3 bittle_cli.py scan
```
This lists Bluetooth LE robots (names ending `_BLE`) and serial ports. Close the Petoi phone app first, because a BLE robot accepts only one connection.

## 2. Connect (pick one)

| Link | Command | Notes |
|---|---|---|
| Bluetooth LE | `python3 bittle_cli.py --ble` | Connects to the first Bittle it finds. Add a name or address to pick a specific one: `--ble Bittle12_BLE` |
| Classic Bluetooth | `python3 bittle_cli.py --serial <port>` | Pair the `…_SSP` device first. The port is `/dev/rfcomm0` (Linux), `/dev/tty.<name>_SSP` (macOS) or `COMx` (Windows) |
| USB cable | `python3 bittle_cli.py --serial /dev/ttyUSB0` | `COMx` on Windows |
| WiFi | `python3 bittle_cli.py --wifi 192.168.1.42` | Your computer and the dog must be on the same network |

WiFi needs firmware built with the web server. Do this once, over USB or Bluetooth:
```bash
python3 bittle_cli.py --serial /dev/ttyUSB0 wifi-setup "MyWifi" "MyPassword"
```
The robot reboots and prints its IP address. Use that address with `--wifi`.

## 3. Use it
Run with no command to open the interactive shell (Tab completes names):
```
bittle> list                         # every combo and chain
bittle> play flipShow                # fused combo (uploaded with K)
bittle> play victoryLap              # chain, run step by step
bittle> chain partyTrick --onboard   # same chain, sent as one q queue the robot runs itself
bittle> play bf                      # any stock skill
bittle> ksit                         # anything else goes to the robot as-is
bittle> stop                         # rest and relax the servos
```

Or run a single command and exit:
```bash
python3 bittle_cli.py --wifi 192.168.1.42 play stuntDog
```

### Make new moves from the shell
```
bittle> mix crazyDog sit hi*2 bf chr zz@40     # fuse skills, save the result, play it (needs --vault)
bittle> seq hello ksit:1 khi:0.5 kwkF:2 kbalance:0  # define a chain (command:seconds)
```
Both are saved to `my_combos.json` and show up in `list` next time. `mix` reads the stored arrays from the vault, so start the CLI with `--vault /path/to/Bittle_Knowledge_Vault`.

Segment modifiers: `hi*2` repeats a skill, `sit~4` runs it slower, `zz@40` holds the last pose for 2 seconds. Gaits (wkF, trF, …) can't be fused, so put them in a `seq` chain instead.

## Safety built in
- Flips, rolls, handstands and jumps run with gyro balancing off (`gb`), which is switched back on (`gB`) afterwards. Otherwise the firmware's automatic self-righting (`rc`) cuts the move short. In step-by-step chains, only the flip steps get this, so walking and trotting keep the gyro on. Pass `--keep-gyro` to turn this off.
- The CLI waits for the robot to confirm each command (it echoes the token back) before sending the next one.
- `mix` refuses combos longer than 125 frames (the ESP32 upload limit) and slows the move into any big pose change.

Tested against a simulated robot over serial and WiFi (WebSocket). **Not yet tested on a real Bittle, and BLE has not been tested at all.** Try new combos on a soft surface first.

---

# Handstand and rear stand (needs a firmware change)

The stock firmware can't hold a two-leg stand: its gyro balancing is tuned for four legs, and it streams tilt only 5 times a second. `firmware/` adds a stand mode on a new serial command, `y`.

| File | What it is |
|---|---|
| `firmware/balanceStand.h` | The stand mode: climb into a handstand or onto the hind legs, hold the top pose, catch falls, optional PID, tilt telemetry |
| `firmware/balance_stand.patch` | Adds that file and hooks it in (`OpenCatEsp32.ino`, `src/OpenCat.h`, `src/reaction.h`) |
| `sim/stand_sim.py` | Side-view physics model used to decide what the controller should do |

## 1. Flash it
1. Get the OpenCatEsp32 source at the commit the vault pins, `84dd6eff307eb2f4af6f9cbdf72f04e7d71beecf`. A newer commit may still accept the patch with small offsets.
2. Apply the patch from the source folder:
   ```bash
   patch -p1 < /path/to/firmware/balance_stand.patch
   ```
3. Build and upload `OpenCatEsp32.ino` over USB with the Arduino IDE, the same way as Petoi's normal firmware upload for the BiBoard.
4. Check that it worked: run `y?` in the CLI. It should reply with a line starting `#P mode`.

The patch applies cleanly and the module compiles and passes its tests on a PC with stand-ins for the firmware functions. **It has not been built for the ESP32 or run on a robot**, because the Arduino and Espressif download servers were blocked where it was written. Expect to fix small compile errors the first time.

## 2. What the simulation says (read this before tuning)
On two legs, the dog stands only while its weight stays over the paws' small contact patch. The model gives the following ("pose window" = how far off the top pose can be and still stand):

| Paw contact length | Pose window | Shove survived, no control | Shove survived, PID on pitch |
|---|---|---|---|
| 4 mm | ±1° | 1.2 mN s | falls |
| 8 mm | ±3° | 5.9 mN s | falls |
| 16 mm | ±6° | 15 mN s | falls |
| 50 mm | ±21° | 55 mN s | 41 mN s |

Once the weight passes the paw's edge, the paw turns into a pivot. Moving a shoulder then mostly swings the light leg, not the body, and the dog has no ankle to push back with. So, in this model, fast PID doesn't save a tip, and sensor noise passed into the shoulders makes things worse. Over WiFi, the PID that helps on 50 mm contact fails completely.

What does help:
1. **An accurate top pose**, with the weight centred over the paws.
2. **A longer contact**, such as resting on the lower legs (shins), or paw pads.
3. **A good fall catch**: on a tip, the mode drops the dog onto four legs.

That's why the firmware's default gains are 0: it holds the pose and catches falls. The model is rigid and planar, with flat paws and estimated masses. Real rubber paws and servo give can behave differently, so the PID is there for you to test.

## 3. Tune it
Use a soft surface and keep a hand ready to catch.

```
bittle> stand hand            # or: stand rear
bittle> stand watch 30        # live tilt: | = tilt error, * = correction
bittle> stand pose 8 52       # trim joints 1–2° at a time until the paws stay flat untouched
bittle> stand pose 9 52
```
Joints: 8/9 = front shoulders, 10/11 = back shoulders, 12/13 = front knees, 14/15 = back knees, 0 = head. Trims are remembered for the next `stand hand` / `stand rear` until the robot reboots. Write the good numbers down, or put them in `handstandEntry` / `rearEntry` in `balanceStand.h`.

The climb sequences come from the stock `hds` (handstand) and `hu` (hands up) skills. Check that the last pose of `stand rear` really is up on the hind legs; you may need to trim it from there.

**Trying the PID:**
1. `stand gains 1 0 0`, hold the robot in its stand, and tilt it slightly by hand. The support shoulders should move to bring the paws back under the body. If they move the other way, run `stand sign -1`.
2. With the robot held balanced and paws flat, run `stand zero`.
3. Raise `kp` in small steps, then add `kd`. `stand mix 1` (or `-1`) uses the support-leg tilt instead of body pitch.
4. Record each try with `stand watch 20 try1.csv` and compare.

**PID on the laptop** (USB or BLE, not WiFi): `stand laptop KP KI KD SECONDS`. The robot streams tilt about 50 times a second and the CLI sends corrections back. This is good for quick experiments without re-flashing. It's slower than the onboard loop.

All stand commands: type `stand` in the shell. Raw firmware commands (`yh`, `yp 1 0 0.05`, `y?` …) are listed at the top of `balanceStand.h`.
