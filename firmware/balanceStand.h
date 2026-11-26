// balanceStand.h - closed-loop handstand and hind-leg (rear) stand for OpenCatEsp32 Bittle.
//
// Standing on two paws is statically stable only while the weight stays over the paws' small
// contact patch. This mode holds a tunable top pose, streams tilt telemetry for tuning, catches
// falls by dropping onto four legs, and offers a PID on body pitch / support-leg tilt that drives
// the support shoulders once per IMU sample. The PID is OFF by default (all gains 0): a planar
// simulation (sim/stand_sim.py) found that fast shoulder feedback cannot stop a tip once the weight
// passes the paw edge, so enable it only to experiment on the real robot.
//
// Serial token 'y' (text). Every subcommand is one letter plus optional numbers:
//   yh            handstand: entry keyframes (from the hds skill), then balance
//   yr            rear stand on the hind legs: entry keyframes (from the hu skill), then balance
//   yg            balance from the current pose (after you put the robot in a stand by hand or by a skill)
//   yx            stop balancing and hold the pose. Any non-'y' command (ksit, d, ...) also stops it
//   yz            setpoint = current pitch (hold the robot balanced in your hand, send yz, let go)
//   ya DEG        setpoint = DEG (absolute pitch). Until yz or ya, each stand uses its starting pitch
//   yp KP KI KD   PID gains, in degrees of shoulder rotation per degree of pitch error
//   ys SIGN       +1 or -1: direction of the correction (find it with the push test in the README)
//   ym MIX        error = pitch - setpoint - MIX x (correction already applied). 0 = body pitch,
//                 +1 or -1 = support-leg tilt (the sign depends on how the joint turns the body)
//   yc 0|1        on a fall, drop onto four legs (default 1) or just stop
//   yl LIM FALL   max correction (deg) and the pitch error (deg) that counts as a fall
//   yf ALPHA      derivative low-pass, 0..1 (1 = unfiltered)
//   yw AIR KNEE ROLL   extra gains: swing the airborne legs (AIR x u), bend support knees (KNEE x u),
//                      differential support knees against roll error (ROLL x roll)
//   yb IDX DEG    change one joint of the base pose (0..15); yB copies the current pose into it
//   yt N          telemetry every N control ticks (0 = off). Lines: "#B ms pitch err u roll"
//   ye 0|1        external control: the laptop sends the correction with yu instead of the PID
//   yu U          external correction in degrees (only while ye 1)
//   y0            smoothly move into the RL standing pose (0 deg shoulders, +23 deg knees)
//   yS [N]        dry-run RL telemetry every N 50 Hz ticks (reads IMU & prints 8 targets without moving)
//   yR            run onboard 50 Hz RL handstand policy (rlHandstand.h)
//   y?            print every parameter
#pragma once
#include <math.h>
#include <stdio.h>
#include "rlHandstand.h"

#define T_BALANCE_STAND 'y'

// ---------------------------------------------------------------- pure controller (host-testable)
struct StandPID {
  float kp = 0, ki = 0, kd = 0;            // deg of joint per deg of error; 0 = hold the pose only
  float sign = 1;                          // flips the correction direction
  float limit = 30;                        // |u| clamp, degrees
  float dAlpha = 0.35f;                    // derivative low-pass, 0..1
  float integ = 0, prevErr = 0, dFilt = 0;
  bool first = true;

  void reset() {
    integ = 0;
    dFilt = 0;
    first = true;
  }

  float update(float err, float dt) {
    if (dt <= 0) dt = 0.001f;
    float d = first ? 0 : (err - prevErr) / dt;
    first = false;
    prevErr = err;
    dFilt += dAlpha * (d - dFilt);
    float pd = kp * err + kd * dFilt;
    // Conditional integration: stop accumulating while the output is saturated (anti-windup).
    float iNext = integ + err * dt;
    if (fabsf(pd + ki * iNext) < limit) integ = iNext;
    float u = sign * (pd + ki * integ);
    return u > limit ? limit : (u < -limit ? -limit : u);
  }
};

#ifndef BALANCE_STAND_HOST_TEST  // ---------------------------------------- firmware glue

enum StandState : uint8_t { STAND_OFF, STAND_ON, STAND_RL, STAND_RL_DRY };

// Keyframes: 16 joint angles + speed (the behavior-frame speed field, deg per step / 8 like skill.h).
// Handstand frames 0-4 come from the hds behavior in InstinctBittleESP.h; the base pose averages
// its two alternating top frames. Rear stand frames 0-4 come from the hu (hands up) behavior.
const int8_t handstandEntry[][DOF + 1] = {
  {  0, 0, 0, 0, 0, 0, 0, 0,  30,  30,  30,  30,  30,  30,  30,  30,  8 },
  { 82, 0, 0, 0, 0, 0, 0, 0, 112, 112,  30,  30,  30,  30,  30,  30,  8 },
  { 82, 0, 0, 0, 0, 0, 0, 0,  50,  50,   0,   0,   0,   0,   0,   0, 12 },
  { 82, 0, 0, 0, 0, 0, 0, 0,  50,  50,  81,  81,   0,   0,   0,   0, 16 },
  { 85, 0, 0, 0, 0, 0, 0, 0,  50,  50, 100, 100,   0,   0,  38,  38, 32 },
};
const int8_t rearEntry[][DOF + 1] = {
  {  0,   0,  0, 0, 0, 0, 0, 0, 30, 30, 30, 30, 30, 30,  30,  30,  8 },
  { 39, -22, 22, 0, 0, 0, 0, 0, 30, 30, 74, 74, 74, 74, -14, -14, 12 },
  { 26, -22, 22, 0, 0, 0, 0, 0, 30, 30, 31,  3, 91, 74, -14,  32, 12 },
  {  9, -22, 22, 0, 0, 0, 0, 0, 35, 35,  3,  3, 85, 85,  43,  43, 12 },
  {  9, -22, 22, 0, 0, 0, 0, 0, 35, 35, 40, 40, 85, 85,  21,  21,  8 },
};

struct StandCtl {
  StandState state = STAND_OFF;
  StandPID pid;
  char mode = 'g';             // 'h' handstand, 'r' rear, 'g' generic (current pose)
  int base[DOF];               // pose the corrections are added to
  int8_t support[2] = { 8, 9 }, air[2] = { 10, 11 }, supportKnee[2] = { 12, 13 };
  float setpoint = 0, fallLimit = 35, mix = 0;
  bool setpointSet = false;    // false: take the tilt at the moment the stand starts
  bool catchFall = true;
  float airGain = 0, kneeGain = 0, rollGain = 0;
  bool external = false;
  float uExt = 0, u = 0;
  int teleEvery = 0;
  unsigned long ticks = 0, lastMicros = 0, fallSince = 0;
  bool savedGyroBalance = true;
  int modeBase[2][DOF];        // tuned top pose per mode: [0] handstand, [1] rear stand
  bool modeBaseSet[2] = { false, false };
  RlHandstandEngine rl;
  unsigned long rlTicks = 0;
  int rlTeleEvery = 5;
} stand;

void standSelectLegs(char mode) {
  bool hand = mode == 'h';  // handstand stands on the front legs, rear stand on the hind legs
  stand.support[0] = hand ? 8 : 10;
  stand.support[1] = hand ? 9 : 11;
  stand.air[0] = hand ? 10 : 8;
  stand.air[1] = hand ? 11 : 9;
  stand.supportKnee[0] = hand ? 12 : 14;
  stand.supportKnee[1] = hand ? 13 : 15;
}

void standPrintParams() {
  char buf[200];
  snprintf(buf, sizeof(buf),
           "#P mode %c on %d kp %.3f ki %.3f kd %.3f sign %.0f mix %.2f lim %.0f fall %.0f dA %.2f air %.2f knee %.2f roll %.2f sp %.1f ext %d tele %d catch %d",
           stand.mode, stand.state == STAND_ON, stand.pid.kp, stand.pid.ki, stand.pid.kd, stand.pid.sign, stand.mix, stand.pid.limit,
           stand.fallLimit, stand.pid.dAlpha, stand.airGain, stand.kneeGain, stand.rollGain, stand.setpoint, stand.external,
           stand.teleEvery, stand.catchFall);
  printToAllPorts(buf);
  String pose = "#Q";
  for (int i = 0; i < DOF; i++) pose += " " + String(stand.base[i]);
  printToAllPorts(pose);
}

void standStop(const char *why) {
  if (stand.state == STAND_OFF) return;
  stand.state = STAND_OFF;
  gyroBalanceQ = stand.savedGyroBalance;
  printToAllPorts(String("#B stop ") + why);
}

const int8_t fourLegPose[DOF] = { 0, 0, 0, 0, 0, 0, 0, 0, 30, 30, 30, 30, 30, 30, 30, 30 };
const int8_t rlStandPose[DOF] = { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 23, 23, 23, 23 };

void standCatch() {  // fast move to the four-leg stand so the robot lands on its feet, not its back
  int target[DOF];
  for (int i = 0; i < DOF; i++) target[i] = fourLegPose[i];
  transform(target, 1, 4);
}

void rlMoveStandPose() {
  stand.savedGyroBalance = gyroBalanceQ;
  gyroBalanceQ = false;
  int target[DOF];
  for (int i = 0; i < DOF; i++) target[i] = rlStandPose[i];
  transform(target, 1, 2);
}

void rlStart(bool dryRun, int teleEveryOverride = -1) {
  if (!updateGyroQ) {
    printToAllPorts("#B error: IMU updates are off (send gU)");
    return;
  }
  stand.savedGyroBalance = gyroBalanceQ;
  gyroBalanceQ = false;
  imuSkip = IMU_SKIP;
  frame = 0;
  if (!dryRun) {
    int target[DOF];
    for (int i = 0; i < DOF; i++) target[i] = rlStandPose[i];
    transform(target, 1, 2);
    delay(150);
  }
  float gIn[3] = { imuGyroRad[0], imuGyroRad[1], imuGyroRad[2] };
  float uIn[3] = { imuWorldUp[0], imuWorldUp[1], imuWorldUp[2] };
  float angUsd[3], gravUsd[3];
  stand.rl.imuToUsd(gIn, uIn, angUsd, gravUsd);
  stand.rl.reset(angUsd, gravUsd);
  stand.rlTicks = 0;
  if (teleEveryOverride >= 0) stand.rlTeleEvery = teleEveryOverride;
  else if (dryRun && stand.rlTeleEvery <= 0) stand.rlTeleEvery = 5;
  stand.fallSince = 0;
  stand.lastMicros = micros();
  stand.state = dryRun ? STAND_RL_DRY : STAND_RL;
  printToAllPorts(dryRun ? "#RL start dry" : "#RL start live");
}

void standStart(char mode) {
  if (!updateGyroQ) {
    printToAllPorts("#B error: IMU updates are off (send gU)");
    return;
  }
  stand.savedGyroBalance = gyroBalanceQ;
  gyroBalanceQ = false;  // no reflexes (lifted/flipped reactions) and no posture adjust() while balancing
  imuSkip = IMU_SKIP;
  frame = 0;
  stand.mode = mode;
  if (mode == 'h' || mode == 'r') {
    standSelectLegs(mode);
    const int8_t(*keys)[DOF + 1] = mode == 'h' ? handstandEntry : rearEntry;
    int n = mode == 'h' ? sizeof(handstandEntry) / sizeof(handstandEntry[0]) : sizeof(rearEntry) / sizeof(rearEntry[0]);
    byte m = mode == 'h' ? 0 : 1;
    if (!stand.modeBaseSet[m]) {  // first use: the last keyframe is the top pose
      for (int i = 0; i < DOF; i++) stand.modeBase[m][i] = keys[n - 1][i];
      stand.modeBaseSet[m] = true;
    }
    int target[DOF];
    for (int k = 0; k < n; k++) {  // the last keyframe is replaced by the (possibly tuned) top pose
      for (int i = 0; i < DOF; i++) target[i] = k == n - 1 ? stand.modeBase[m][i] : keys[k][i];
      transform(target, 1, keys[k][DOF] / 8.0);
    }
    for (int i = 0; i < DOF; i++) stand.base[i] = stand.modeBase[m][i];
  } else {
    for (int i = 0; i < DOF; i++) stand.base[i] = currentAng[i];
  }
  if (!stand.setpointSet) stand.setpoint = ypr[1];
  stand.pid.reset();
  stand.uExt = 0;
  stand.u = 0;
  stand.ticks = 0;
  stand.fallSince = 0;
  stand.lastMicros = micros();
  stand.state = STAND_ON;
  printToAllPorts(String("#B start ") + mode);
}

void standApply(float u, float rollErr) {
  for (byte s = 0; s < 2; s++) {
    calibratedPWM(stand.support[s], stand.base[stand.support[s]] + u);
    if (stand.airGain != 0)
      calibratedPWM(stand.air[s], stand.base[stand.air[s]] + stand.airGain * u);
    if (stand.kneeGain != 0 || stand.rollGain != 0) {
      float rollPart = (s == 0 ? 1 : -1) * stand.rollGain * rollErr;
      calibratedPWM(stand.supportKnee[s], stand.base[stand.supportKnee[s]] + stand.kneeGain * u + rollPart);
    }
  }
}

// Called from loop() every pass. Runs one control tick per new IMU sample (the IMU task updates every ~5 ms).
void balanceLoop() {
  if (stand.state == STAND_OFF) return;
  if (stand.state == STAND_RL || stand.state == STAND_RL_DRY) {
    unsigned long now = micros();
    if ((unsigned long)(now - stand.lastMicros) < RL_STEP_PERIOD_US) return;
    stand.lastMicros = now;
    idleTimer = millis();

    float gIn[3] = { imuGyroRad[0], imuGyroRad[1], imuGyroRad[2] };
    float uIn[3] = { imuWorldUp[0], imuWorldUp[1], imuWorldUp[2] };
    float angUsd[3], gravUsd[3];
    stand.rl.imuToUsd(gIn, uIn, angUsd, gravUsd);

    if (stand.state == STAND_RL && stand.catchFall && (fabsf(gravUsd[0]) > 0.85f || gravUsd[2] > 0.75f)) {
      if (!stand.fallSince) stand.fallSince = millis();
      if (millis() - stand.fallSince > 120) {
        standStop("rl_fall");
        standCatch();
        return;
      }
    } else {
      stand.fallSince = 0;
    }

    float ocDeg[16];
    float act[RL_ACT_DIM];
    stand.rl.step(gIn, uIn, ocDeg, act);
    if (stand.state == STAND_RL) {
      for (int j = 0; j < RL_ACT_DIM; ++j) {
        calibratedPWM(RL_JOINT_OC_IDX[j], ocDeg[RL_JOINT_OC_IDX[j]]);
      }
    }
    int teleN = stand.state == STAND_RL_DRY ? max(1, stand.rlTeleEvery) : stand.teleEvery;
    if (teleN > 0 && ++stand.rlTicks % teleN == 0) {
      char buf[160];
      snprintf(buf, sizeof(buf),
               "#RL g=(%.2f,%.2f,%.2f) w=(%.2f,%.2f,%.2f) deg=(%.0f,%.0f,%.0f,%.0f,%.0f,%.0f,%.0f,%.0f)",
               gravUsd[0], gravUsd[1], gravUsd[2], angUsd[0], angUsd[1], angUsd[2],
               ocDeg[8], ocDeg[9], ocDeg[10], ocDeg[11], ocDeg[12], ocDeg[13], ocDeg[14], ocDeg[15]);
      printToAllPorts(buf);
    }
    return;
  }
  unsigned long now = micros();
  float dt = (now - stand.lastMicros) * 1e-6f;
  if (dt < IMU_PERIOD * 1e-3f) return;
  stand.lastMicros = now;
  idleTimer = millis();  // keep random-mind idle behaviors from starting mid-stand

  float pitch = ypr[1], roll = ypr[2];
  float err = pitch - stand.setpoint - stand.mix * stand.u;  // mix != 0: support-leg tilt instead of body pitch
  if (fabsf(pitch - stand.setpoint) > stand.fallLimit) {
    if (!stand.fallSince) stand.fallSince = millis();
    if (millis() - stand.fallSince > 60) {
      standStop("fall");
      if (stand.catchFall) standCatch();
      return;
    }
  } else
    stand.fallSince = 0;

  float u = stand.external ? stand.uExt : stand.pid.update(err, dt);
  if (stand.external) stand.pid.prevErr = err;
  stand.u = u;
  standApply(u, roll);

  if (stand.teleEvery > 0 && ++stand.ticks % stand.teleEvery == 0) {
    char buf[64];
    snprintf(buf, sizeof(buf), "#B %lu %.2f %.2f %.2f %.2f", millis(), pitch, err, u, roll);
    printToAllPorts(buf);
  }
}

// Handles the 'y' token. newCmd holds the text after the token, e.g. "p 1.2 0.4 0.05".
void standCommand(const char *cmd) {
  while (*cmd == ' ') cmd++;
  char sub = *cmd;
  const char *args = sub ? cmd + 1 : cmd;
  float a = 0, b = 0, c = 0;
  int n = sscanf(args, "%f %f %f", &a, &b, &c);
  switch (sub) {
    case 'h':
    case 'r':
    case 'g': standStart(sub); break;
    case 'x': standStop("user"); break;
    case 'z': stand.setpoint = ypr[1]; stand.setpointSet = true; stand.pid.reset(); break;
    case 'a': if (n >= 1) { stand.setpoint = a; stand.setpointSet = true; stand.pid.reset(); } break;
    case 'p':
      if (n >= 1) stand.pid.kp = a;
      if (n >= 2) stand.pid.ki = b;
      if (n >= 3) stand.pid.kd = c;
      break;
    case 's': if (n >= 1) stand.pid.sign = a < 0 ? -1 : 1; break;
    case 'm': if (n >= 1) stand.mix = a; break;
    case 'c': if (n >= 1) stand.catchFall = a != 0; break;
    case 'l':
      if (n >= 1) stand.pid.limit = fabsf(a);
      if (n >= 2) stand.fallLimit = fabsf(b);
      break;
    case 'f': if (n >= 1) stand.pid.dAlpha = fmaxf(0.01f, fminf(1.0f, a)); break;
    case 'w':
      if (n >= 1) stand.airGain = a;
      if (n >= 2) stand.kneeGain = b;
      if (n >= 3) stand.rollGain = c;
      break;
    case 'b':  // also remembered as this mode's top pose for the next yh / yr
      if (n >= 2 && a >= 0 && a < DOF) {
        stand.base[int(a)] = int(b);
        if (stand.mode != 'g') {
          byte m = stand.mode == 'h' ? 0 : 1;
          if (stand.modeBaseSet[m]) stand.modeBase[m][int(a)] = int(b);
        }
        if (stand.state == STAND_OFF) calibratedPWM(int(a), b);
      }
      break;
    case 'B': for (int i = 0; i < DOF; i++) stand.base[i] = currentAng[i]; break;
    case 't': if (n >= 1) stand.teleEvery = max(0, int(a)); break;
    case 'e': if (n >= 1) { stand.external = a != 0; stand.uExt = 0; } break;
    case 'u': if (n >= 1) stand.uExt = fmaxf(-stand.pid.limit, fminf(stand.pid.limit, a)); break;
    case '0': rlMoveStandPose(); break;
    case 'S': rlStart(true, n >= 1 ? max(0, int(a)) : 5); break;
    case 'R': rlStart(false, n >= 1 ? max(0, int(a)) : 0); break;
    case '?': standPrintParams(); break;
    default: printToAllPorts("#B unknown y subcommand"); break;
  }
}

#endif  // BALANCE_STAND_HOST_TEST
