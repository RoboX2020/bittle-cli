#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${OPENCAT_DIR:-/home/robotics/isaac/OpenCatEsp32}"
ARDUINO_CLI="${ARDUINO_CLI:-$HOME/.local/bin/arduino-cli}"
FQBN="esp32:esp32:esp32:FlashFreq=80,FlashMode=qio,FlashSize=4M,PartitionScheme=huge_app,CPUFreq=240,UploadSpeed=921600"

PORT="${1:-}"
BOARD="${2:-auto}"

if [[ -z "${PORT}" ]]; then
  for dev in /dev/ttyUSB* /dev/ttyACM*; do
    if [[ -e "$dev" ]]; then
      PORT="$dev"
      break
    fi
  done
fi

if [[ -z "${PORT}" || ! -e "${PORT}" ]]; then
  echo "ERROR: No USB serial port found (/dev/ttyUSB* or /dev/ttyACM*)."
  echo "Make sure Bittle X is powered ON and plugged into the BiBoard ESP32 USB-C data port (not the belly battery-charging USB port)."
  exit 1
fi

if [[ "${BOARD}" == "auto" ]]; then
  BOARD="$(python3 - "${PORT}" <<'PY'
import sys, time, serial
port = sys.argv[1]
try:
    with serial.Serial(port, 115200, timeout=0.4) as s:
        time.sleep(0.4)
        s.reset_input_buffer()
        s.write(b"?\n")
        time.sleep(0.6)
        raw = s.read(512).decode(errors="replace")
    if "B02" in raw:
        print("BiBoard_V0_2")
    elif "B01" in raw:
        print("BiBoard_V0_1")
    elif "B10" in raw:
        print("BiBoard_V1_0")
    else:
        print("UNKNOWN")
except Exception as e:
    print("ERROR:" + str(e))
PY
)"
  echo "[flash_rl_handstand] Auto-detected board: ${BOARD} on ${PORT}"
fi

case "${BOARD}" in
  BiBoard_V1_0|B10)
    BUILD_DIR="${REPO_DIR}/build_v1_0"
    BOARD_DEF="BiBoard_V1_0"
    ;;
  BiBoard_V0_2|B02)
    BUILD_DIR="${REPO_DIR}/build_v0_2"
    BOARD_DEF="BiBoard_V0_2"
    ;;
  *)
    echo "ERROR: Could not confirm BiBoard revision (${BOARD})."
    echo "Pass board explicitly as second arg: $0 ${PORT} BiBoard_V1_0  (or BiBoard_V0_2)"
    exit 1
    ;;
esac

if [[ ! -f "${BUILD_DIR}/OpenCatEsp32.ino.bin" ]]; then
  echo "[flash_rl_handstand] Compiling ${BOARD_DEF} into ${BUILD_DIR}..."
  python3 - "${REPO_DIR}/OpenCatEsp32.ino" "${BOARD_DEF}" <<'PY'
import sys
p, b = sys.argv[1], sys.argv[2]
txt = open(p).read()
for name in ("BiBoard_V0_1", "BiBoard_V0_2", "BiBoard_V1_0", "BiBoard2"):
    txt = txt.replace(f"#define {name}", f"// #define {name}")
    txt = txt.replace(f"// // #define {name}", f"// #define {name}")
txt = txt.replace(f"// #define {b}", f"#define {b}", 1)
open(p, "w").write(txt)
PY
  "${ARDUINO_CLI}" compile --fqbn "${FQBN}" --output-dir "${BUILD_DIR}" "${REPO_DIR}/OpenCatEsp32.ino"
fi

echo "[flash_rl_handstand] Uploading ${BUILD_DIR}/OpenCatEsp32.ino.bin to ${PORT}..."
"${ARDUINO_CLI}" upload -p "${PORT}" --fqbn "${FQBN}" --input-dir "${BUILD_DIR}"
echo "[flash_rl_handstand] Upload complete!"
