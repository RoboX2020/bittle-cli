# Bittle Terminal Controller

A command-line tool to operate and script motions for Petoi Bittle quadrupeds.

## System Setup

### Linux
1. Install Python 3 and dependencies:
   ```bash
   sudo apt update && sudo apt install -y python3 python3-pip bluez
   ```
2. Grant user access to serial ports:
   ```bash
   sudo usermod -a -G dialout $USER
   ```
   Log out and log back in for changes to apply.

### macOS
1. Install Python 3 using Homebrew or the official installer.
2. Grant Bluetooth permission to your terminal application in System Settings -> Privacy & Security -> Bluetooth.

### Windows
1. Install Python 3.8+ and select 'Add Python to PATH'.
2. Ensure Bluetooth is enabled. For USB serial, install CH340 or CP210x drivers if prompted.

## Installation

Clone and install dependencies:
```bash
git clone https://github.com/RoboX2020/bittle-cli.git
cd bittle-cli
pip install -e .
```

## Usage

### 1. Discover devices
```bash
bittle scan
```

### 2. Connect
- Over Bluetooth LE:
  ```bash
  bittle --ble
  ```
- Over USB serial:
  ```bash
  bittle --serial /dev/ttyUSB0
  ```
- Over WiFi WebSocket:
  ```bash
  bittle --wifi 192.168.1.100
  ```

### 3. Interactive Shell
Launch the connection command to enter the shell. Common commands:
- `list`: Show available combos and chains
- `play <name>`: Run a skill or combo (e.g. `play flipShow`)
- `chain <name>`: Run a movement sequence (e.g. `chain partyTrick`)
- `stop`: Relax servos
- `quit`: Exit shell

### 4. Running Without Physical Hardware
You can test the tool on any machine using the built-in simulator:
```bash
python3 test_bittle.py
```
