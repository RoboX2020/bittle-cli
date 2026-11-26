// rlHandstand.h - Onboard 50 Hz RL handstand actor inference engine for OpenCatEsp32.
// Evaluates the 1:1 real-scale Asymmetric Actor-Critic policy (IMU + action history -> 8 DoFs).
#pragma once

#include <math.h>
#include <stdint.h>
#include "rlHandstandWeights.h"

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

struct RlHandstandEngine {
  float angHist[RL_HIST_LEN][3];
  float gravHist[RL_HIST_LEN][3];
  float actHist[RL_HIST_LEN][RL_ACT_DIM];
  float lastAct[RL_ACT_DIM];
  // Scratch buffers kept off the ESP32 loopTask stack (~1.8 KB total).
  mutable float xNorm_[RL_OBS_DIM];
  mutable float h1_[RL_H1];
  mutable float h2_[RL_H2];
  mutable float h3_[RL_H3];

  static inline float elu(float x) {
    return x > 0.0f ? x : expf(x) - 1.0f;
  }

  static inline float clampf(float x, float lo, float hi) {
    return x < lo ? lo : (x > hi ? hi : x);
  }

  // Convert OpenCat BiBoard IMU frame (+X head, +Y left, +Z up) to bittle.usd frame
  // (+X right, +Y head, +Z up). worldUpImu is world +Z expressed in OpenCat IMU frame.
  static void imuToUsd(
      const float gyroImuRad[3],
      const float worldUpImu[3],
      float angUsdOut[3],
      float projGravUsdOut[3]) {
    angUsdOut[0] = -gyroImuRad[1];
    angUsdOut[1] = gyroImuRad[0];
    angUsdOut[2] = gyroImuRad[2];

    float norm = sqrtf(
        worldUpImu[0] * worldUpImu[0] +
        worldUpImu[1] * worldUpImu[1] +
        worldUpImu[2] * worldUpImu[2]);
    float inv = norm > 1e-6f ? (1.0f / norm) : 1.0f;
    float ux = worldUpImu[0] * inv;
    float uy = worldUpImu[1] * inv;
    float uz = worldUpImu[2] * inv;
    // projected_gravity = -world_up in bittle.usd body frame
    projGravUsdOut[0] = uy;
    projGravUsdOut[1] = -ux;
    projGravUsdOut[2] = -uz;
  }

  void reset(const float angUsd[3], const float projGravUsd[3]) {
    for (int t = 0; t < RL_HIST_LEN; ++t) {
      for (int i = 0; i < 3; ++i) {
        angHist[t][i] = angUsd[i];
        gravHist[t][i] = projGravUsd[i];
      }
      for (int j = 0; j < RL_ACT_DIM; ++j) {
        actHist[t][j] = 0.0f;
      }
    }
    for (int j = 0; j < RL_ACT_DIM; ++j) {
      lastAct[j] = 0.0f;
    }
  }

  void buildObs(const float angUsd[3], const float projGravUsd[3], float obsOut[RL_OBS_DIM]) {
    for (int t = 0; t < RL_HIST_LEN - 1; ++t) {
      for (int i = 0; i < 3; ++i) {
        angHist[t][i] = angHist[t + 1][i];
        gravHist[t][i] = gravHist[t + 1][i];
      }
    }
    for (int i = 0; i < 3; ++i) {
      angHist[RL_HIST_LEN - 1][i] = angUsd[i];
      gravHist[RL_HIST_LEN - 1][i] = projGravUsd[i];
    }

    int idx = 0;
    for (int t = 0; t < RL_HIST_LEN; ++t) {
      for (int i = 0; i < 3; ++i) obsOut[idx++] = angHist[t][i];
    }
    for (int t = 0; t < RL_HIST_LEN; ++t) {
      for (int i = 0; i < 3; ++i) obsOut[idx++] = gravHist[t][i];
    }
    for (int t = 0; t < RL_HIST_LEN; ++t) {
      for (int j = 0; j < RL_ACT_DIM; ++j) obsOut[idx++] = actHist[t][j];
    }
  }

  void pushAction(const float act[RL_ACT_DIM]) {
    for (int t = 0; t < RL_HIST_LEN - 1; ++t) {
      for (int j = 0; j < RL_ACT_DIM; ++j) {
        actHist[t][j] = actHist[t + 1][j];
      }
    }
    for (int j = 0; j < RL_ACT_DIM; ++j) {
      actHist[RL_HIST_LEN - 1][j] = act[j];
      lastAct[j] = act[j];
    }
  }

  void forwardRaw(const float obs[RL_OBS_DIM], float actOut[RL_ACT_DIM]) const {
    for (int i = 0; i < RL_OBS_DIM; ++i) {
      float s = RL_OBS_STD[i] > 1e-6f ? RL_OBS_STD[i] : 1.0f;
      xNorm_[i] = (obs[i] - RL_OBS_MEAN[i]) / s;
    }

    for (int r = 0; r < RL_H1; ++r) {
      float acc = RL_B0[r];
      const float *row = &RL_W0[r * RL_OBS_DIM];
      for (int c = 0; c < RL_OBS_DIM; ++c) acc += row[c] * xNorm_[c];
      h1_[r] = elu(acc);
    }

    for (int r = 0; r < RL_H2; ++r) {
      float acc = RL_B2[r];
      const float *row = &RL_W2[r * RL_H1];
      for (int c = 0; c < RL_H1; ++c) acc += row[c] * h1_[c];
      h2_[r] = elu(acc);
    }

    for (int r = 0; r < RL_H3; ++r) {
      float acc = RL_B4[r];
      const float *row = &RL_W4[r * RL_H2];
      for (int c = 0; c < RL_H2; ++c) acc += row[c] * h2_[c];
      h3_[r] = elu(acc);
    }

    for (int r = 0; r < RL_ACT_DIM; ++r) {
      float acc = RL_B6[r];
      const float *row = &RL_W6[r * RL_H3];
      for (int c = 0; c < RL_H3; ++c) acc += row[c] * h3_[c];
      actOut[r] = clampf(acc, -RL_ACT_CLIP, RL_ACT_CLIP);
    }
  }

  static void actionToOpenCatDeg(const float act[RL_ACT_DIM], float ocDegOut[16]) {
    for (int i = 0; i < 16; ++i) ocDegOut[i] = 0.0f;
    constexpr float kRadToDeg = 180.0f / float(M_PI);
    for (int j = 0; j < RL_ACT_DIM; ++j) {
      float qRad = RL_DEFAULT_RAD[j] + RL_ACT_SCALE * act[j];
      ocDegOut[RL_JOINT_OC_IDX[j]] = RL_JOINT_OC_SIGN[j] * (qRad * kRadToDeg);
    }
  }

  void step(const float gyroImuRad[3], const float worldUpImu[3], float ocDegOut[16], float actOut[RL_ACT_DIM]) {
    float angUsd[3];
    float gravUsd[3];
    float obs[RL_OBS_DIM];
    imuToUsd(gyroImuRad, worldUpImu, angUsd, gravUsd);
    buildObs(angUsd, gravUsd, obs);
    forwardRaw(obs, actOut);
    pushAction(actOut);
    actionToOpenCatDeg(actOut, ocDegOut);
  }
};
