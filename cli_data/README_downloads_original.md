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
