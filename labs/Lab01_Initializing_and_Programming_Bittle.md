# Lab 01: Initializing & Programming Petoi Bittle Normally

## Learning Objectives
By the end of this lab, you will be able to:
1. Understand the Petoi Bittle / Bittle X (BiBoard ESP32 + `OpenCatEsp32`) hardware, 16-channel joint layout, and IMU architecture.
2. Initialize, calibrate, and test standard postures and skills over USB serial or Bluetooth.
3. Understand OpenCat's ASCII and binary serial wire protocol (`k`, `m`, `d`, `g`, `q`, `K`, `?`).
4. Diagnose factory ROM skill omissions (`?` error token).

---

## 1. Hardware & Coordinate Architecture

Petoi Bittle X runs **OpenCatEsp32** on an ESP32-based **BiBoard** with a 6-axis IMU (`MPU6050`) and hobby PWM servos. Although OpenCat allocates 16 logical servo channels (`0..15`), Bittle's 8-DoF locomotion uses channels `8..15` (plus optional head pan/tilt on `0`/`1`):

| OpenCat Channel | Physical Joint | Notes |
|---|---|---|
| `0` / `1` | Head Pan / Tilt | Optional; affects handstand chin clearance! |
| `8` | Front Left Shoulder (Hip Pitch) | Support leg in handstand |
| `9` | Front Right Shoulder (Hip Pitch) | Support leg in handstand |
| `10` | Back Right Hip (Hip Pitch) | Airborne in handstand |
| `11` | Back Left Hip (Hip Pitch) | Airborne in handstand |
| `12` | Front Left Knee | Support knee in handstand |
| `13` | Front Right Knee | Support knee in handstand |
| `14` | Back Right Knee | Airborne in handstand |
| `15` | Back Left Knee | Airborne in handstand |

---

## 2. Initializing & Calibrating the Robot

### Step 1: Power & USB / Bluetooth Pairing
1. Power Bittle on with a charged 2S LiPo battery (stunts and handstands draw high peak servo current).
2. Close the Petoi mobile app if using BLE—the robot only accepts **one** BLE GATT connection at a time.
3. For USB programming/serial (`115200` baud), connect via USB-C/micro-USB and grant serial permissions on Linux:
   ```bash
   sudo usermod -a -G dialout $USER
   # log out and back in
   ```

### Step 2: Observe the BiBoard Boot Sequence
Whenever a serial or BLE client connects to Bittle X (`PetoiBLE-4CB5`), the ESP32 prints its initialization sequence (observed directly from hardware):
```text
Init IMU
Init servos: 25.37MHz
Load skills
* Start *
Bittle
Ready!
```
> **Important:** Commands sent during the first ~1–4 seconds before `Ready!` arrives are silently dropped by the firmware.

### Step 3: Servo Calibration & Neutral Stand
Before running any custom skill or RL policy, ensure mechanical zero offsets are calibrated (`c` mode in OpenCat) and test basic postures:
```bash
# Put Bittle in neutral standing posture
bittle --ble kbalance

# Sit / wave / relax servos
bittle --ble ksit
bittle --ble khi
bittle --ble stop     # sends 'd' (rest & PWM off)
```

---

## 3. Programming Bittle Normally (OpenCat Wire Protocol)

OpenCatEsp32 accepts single-character command tokens terminated by `\n` (ASCII text) or `~` (binary payload):

| Token | Format | Behavior | Robot Echo |
|---|---|---|---|
| `k<name>` | Text (`ksit\n`) | Run built-in posture, gait, or behavior from ROM | `k` (or `?` if unknown) |
| `m <idx> <deg>` | Text (`m 0 30\n`) | Move single joint `idx` to angle `deg` | `m` |
| `o <count>, ...` | Text | Stream multiple joint targets (`headBang` chain uses `o`) | `o` |
| `d` | Text (`d\n`) | Rest pose and relax all servos | `d` |
| `gb` / `gB` | Text | Disable (`gb`) / enable (`gB`) IMU gyro self-righting | `g` |
| `q<cmd:ms>...` | Text | Onboard timed task queue (e.g. `qksit:800>khi:300>`) | `q` |
| `K<int8 bytes>~` | Binary | Upload custom behavior frame array (up to 125 frames) into RAM | `k` |
| `w%SSID%PASS` | Text | Provision WiFi credentials (reboots and prints IP) | `w` |

---

## 4. Exercise: Diagnosing Missing Factory Skills (`?` Error)

On our physical Bittle X (`PetoiBLE-4CB5`), trying to trigger stock dynamic handstand (`khds`) or hands-up (`khu`) returned:
```text
Robot -> '?\r\nk\r\n'
```
**Why?** The `?` response means **"Unknown Skill"**—`hds` and `hu` were not compiled into that unit's factory flash instinct table (`InstinctBittleESP.h`). Standard skills (`ksit`, `kbalance`, `khi`, `d`) worked normally.

**Takeaway:** When a stock `k<skill>` fails silently or returns `?`, upload the motion keyframes directly into ESP32 RAM using the binary `K` token (covered in **Lab 02**).

---

## Verification Checklist
- [ ] Connected to Bittle (or `bittle-mock`) and observed `Ready!`
- [ ] Executed `ksit`, `kbalance`, and `stop` (`d`)
- [ ] Tested single-joint move `m 0 20` and observed token echo
