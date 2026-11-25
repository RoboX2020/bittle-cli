# Copyright (c) 2026. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause

"""Custom MDP reward and metric terms for 1:1 real-scale Petoi Bittle handstand training."""

from __future__ import annotations

import torch
from typing import TYPE_CHECKING

from isaaclab.assets import Articulation
from isaaclab.managers import ManagerTermBase, SceneEntityCfg
from isaaclab.sensors import ContactSensor

if TYPE_CHECKING:
    from isaaclab.envs import ManagerBasedRLEnv


def handstand_orientation_reward(
    env: ManagerBasedRLEnv,
    std: float = 0.22,
    asset_cfg: SceneEntityCfg = SceneEntityCfg("robot"),
) -> torch.Tensor:
    """Reward pitching forward into a vertical handstand (+Y_body pointing down)."""
    asset: Articulation = env.scene[asset_cfg.name]
    g_b = asset.data.projected_gravity_b.torch
    err_sq = torch.square(g_b[:, 0]) + torch.square(g_b[:, 1] - 1.0) + torch.square(g_b[:, 2])
    coarse = torch.clamp((g_b[:, 1] + 0.1) / 1.1, min=0.0, max=1.0)
    fine = torch.exp(-err_sq / (std * std))
    return 0.20 * coarse + 0.80 * fine


def handstand_height_reward(
    env: ManagerBasedRLEnv,
    target_height: float = 0.105,
    min_height: float = 0.055,
    std: float = 0.025,
    asset_cfg: SceneEntityCfg = SceneEntityCfg("robot"),
) -> torch.Tensor:
    """Reward lifting base_frame_link to true 1:1 Bittle handstand height (~10.5 cm)."""
    asset: Articulation = env.scene[asset_cfg.name]
    g_b = asset.data.projected_gravity_b.torch
    z = asset.data.root_pos_w.torch[:, 2]
    pitch_gate = torch.clamp((g_b[:, 1] - 0.15) / 0.5, min=0.0, max=1.0)
    prog = torch.clamp((z - min_height) / (target_height - min_height), min=0.0, max=1.0)
    peak = torch.exp(-torch.square(z - target_height) / (std * std))
    return pitch_gate * (0.4 * prog + 0.6 * peak)


def rear_above_base_reward(
    env: ManagerBasedRLEnv,
    min_rel_z: float = -0.025,
    target_rel_z: float = 0.055,
    asset_cfg: SceneEntityCfg = SceneEntityCfg("robot", body_names=".*_back_knee_link"),
) -> torch.Tensor:
    """Reward raising rear legs above base_frame_link (1:1 scale, invariant to jumping)."""
    asset: Articulation = env.scene[asset_cfg.name]
    z_base = asset.data.root_pos_w.torch[:, 2]
    z_rear = asset.data.body_pos_w.torch[:, asset_cfg.body_ids, 2].mean(dim=1)
    rel_z = z_rear - z_base
    return torch.clamp((rel_z - min_rel_z) / (target_rel_z - min_rel_z), min=0.0, max=1.0)


def front_knees_elevated_reward(
    env: ManagerBasedRLEnv,
    min_z: float = 0.015,
    target_z: float = 0.045,
    asset_cfg: SceneEntityCfg = SceneEntityCfg("robot", body_names=".*_front_knee_link"),
) -> torch.Tensor:
    """Reward keeping front knee joints elevated off the ground, gated by pitch toward handstand."""
    asset: Articulation = env.scene[asset_cfg.name]
    g_b = asset.data.projected_gravity_b.torch
    pitch_gate = torch.clamp((g_b[:, 1] - 0.30) / 0.50, min=0.0, max=1.0)
    z_knees_min = asset.data.body_pos_w.torch[:, asset_cfg.body_ids, 2].min(dim=1)[0]
    return pitch_gate * torch.clamp((z_knees_min - min_z) / (target_z - min_z), min=0.0, max=1.0)


def front_knees_low_penalty(
    env: ManagerBasedRLEnv,
    safe_z: float = 0.030,
    asset_cfg: SceneEntityCfg = SceneEntityCfg("robot", body_names=".*_front_knee_link"),
) -> torch.Tensor:
    """Penalize dropping front knee joints close to the ground while pitching/holding handstand."""
    asset: Articulation = env.scene[asset_cfg.name]
    g_b = asset.data.projected_gravity_b.torch
    pitch_gate = torch.clamp((g_b[:, 1] - 0.3) / 0.4, min=0.0, max=1.0)
    z_knees_min = asset.data.body_pos_w.torch[:, asset_cfg.body_ids, 2].min(dim=1)[0]
    deficit = torch.clamp((safe_z - z_knees_min) / safe_z, min=0.0, max=1.0)
    return pitch_gate * deficit


def jump_height_penalty(
    env: ManagerBasedRLEnv,
    max_z: float = 0.14,
    asset_cfg: SceneEntityCfg = SceneEntityCfg("robot"),
) -> torch.Tensor:
    """Penalize launching the 1:1 robot body into the air above handstand height (bounded)."""
    asset: Articulation = env.scene[asset_cfg.name]
    z = asset.data.root_pos_w.torch[:, 2]
    return torch.clamp((z - max_z) / 0.10, min=0.0, max=1.0)


def front_feet_support_reward(
    env: ManagerBasedRLEnv,
    front_sensor_cfg: SceneEntityCfg,
    rear_sensor_cfg: SceneEntityCfg,
    shoulder_sensor_cfg: SceneEntityCfg,
    threshold: float = 0.02,
    asset_cfg: SceneEntityCfg = SceneEntityCfg("robot"),
) -> torch.Tensor:
    """Reward front-paw support (rear & shoulders off floor), gated by pitch toward handstand."""
    asset: Articulation = env.scene[asset_cfg.name]
    g_b = asset.data.projected_gravity_b.torch
    pitch_gate = torch.clamp((g_b[:, 1] - 0.35) / 0.45, min=0.0, max=1.0)
    contact_sensor: ContactSensor = env.scene.sensors[front_sensor_cfg.name]
    forces = contact_sensor.data.net_normal_forces_w_history.torch.norm(dim=-1).max(dim=1)[0]
    front_on = forces[:, front_sensor_cfg.body_ids] > threshold
    no_rear = (forces[:, rear_sensor_cfg.body_ids] <= threshold).all(dim=1).float()
    no_shoulder = (forces[:, shoulder_sensor_cfg.body_ids] <= threshold).all(dim=1).float()
    front_frac = front_on.float().mean(dim=1)
    both_front = front_on.all(dim=1).float()
    return pitch_gate * no_rear * no_shoulder * (0.4 * front_frac + 0.6 * both_front)


def handstand_hold_bonus(
    env: ManagerBasedRLEnv,
    front_sensor_cfg: SceneEntityCfg,
    rear_sensor_cfg: SceneEntityCfg,
    shoulder_sensor_cfg: SceneEntityCfg,
    front_knee_cfg: SceneEntityCfg = SceneEntityCfg("robot", body_names=".*_front_knee_link"),
    min_gy: float = 0.85,
    min_z: float = 0.075,
    max_z: float = 0.145,
    min_knee_z: float = 0.030,
    threshold: float = 0.02,
    asset_cfg: SceneEntityCfg = SceneEntityCfg("robot"),
) -> torch.Tensor:
    """Dense bonus when Bittle holds a vertical handstand on front paws with knees off the ground."""
    asset: Articulation = env.scene[asset_cfg.name]
    g_b = asset.data.projected_gravity_b.torch
    z = asset.data.root_pos_w.torch[:, 2]
    z_knees_min = asset.data.body_pos_w.torch[:, front_knee_cfg.body_ids, 2].min(dim=1)[0]
    contact_sensor: ContactSensor = env.scene.sensors[front_sensor_cfg.name]
    forces = contact_sensor.data.net_normal_forces_w_history.torch.norm(dim=-1).max(dim=1)[0]
    both_front = (forces[:, front_sensor_cfg.body_ids] > threshold).all(dim=1)
    no_rear = (forces[:, rear_sensor_cfg.body_ids] <= threshold).all(dim=1)
    no_shoulder = (forces[:, shoulder_sensor_cfg.body_ids] <= threshold).all(dim=1)
    knees_up = z_knees_min > min_knee_z
    holding = (g_b[:, 1] > min_gy) & (z > min_z) & (z < max_z) & both_front & no_rear & no_shoulder & knees_up
    return holding.float()


def handstand_stability_penalty(
    env: ManagerBasedRLEnv,
    min_gy: float = 0.75,
    asset_cfg: SceneEntityCfg = SceneEntityCfg("robot"),
) -> torch.Tensor:
    """Penalize base linear & angular velocity once pitched into a handstand (bounded)."""
    asset: Articulation = env.scene[asset_cfg.name]
    g_b = asset.data.projected_gravity_b.torch
    inverted = (g_b[:, 1] > min_gy).float()
    lin_vel_sq = torch.sum(torch.square(asset.data.root_lin_vel_b.torch), dim=1)
    ang_vel_sq = torch.sum(torch.square(asset.data.root_ang_vel_b.torch), dim=1)
    return inverted * torch.clamp(lin_vel_sq + 0.1 * ang_vel_sq, max=5.0)


class handstand_metrics(ManagerTermBase):
    """Logs handstand progress and strict success rate into env.extras['log']."""

    def __init__(self, cfg, env: ManagerBasedRLEnv):
        super().__init__(cfg, env)
        self._front_cfg: SceneEntityCfg = cfg.params["front_sensor_cfg"]
        self._rear_cfg: SceneEntityCfg = cfg.params["rear_sensor_cfg"]
        self._shoulder_cfg: SceneEntityCfg = cfg.params["shoulder_sensor_cfg"]
        self._knee_cfg: SceneEntityCfg = cfg.params["front_knee_cfg"]
        self._asset: Articulation = env.scene["robot"]
        self._sensor: ContactSensor = env.scene.sensors[self._front_cfg.name]
        self._hold_steps = torch.zeros(env.num_envs, device=env.device)

    def reset(self, env_ids: torch.Tensor) -> None:
        survived = self._env.termination_manager.time_outs[env_ids]
        held_enough = self._hold_steps[env_ids] >= 100.0
        success = survived & held_enough
        log = self._env.extras.setdefault("log", {})
        log["Metrics/handstand_success_rate"] = success.float().mean()
        log["Metrics/handstand_mean_hold_steps"] = self._hold_steps[env_ids].mean()
        self._hold_steps[env_ids] = 0.0

    def __call__(
        self,
        env: ManagerBasedRLEnv,
        front_sensor_cfg: SceneEntityCfg,
        rear_sensor_cfg: SceneEntityCfg,
        shoulder_sensor_cfg: SceneEntityCfg,
        front_knee_cfg: SceneEntityCfg,
        min_gy: float = 0.85,
        min_z: float = 0.075,
        max_z: float = 0.145,
        min_knee_z: float = 0.030,
        threshold: float = 0.02,
    ) -> torch.Tensor:
        g_b = self._asset.data.projected_gravity_b.torch
        z = self._asset.data.root_pos_w.torch[:, 2]
        z_knees_min = self._asset.data.body_pos_w.torch[:, self._knee_cfg.body_ids, 2].min(dim=1)[0]
        forces = self._sensor.data.net_normal_forces_w_history.torch.norm(dim=-1).max(dim=1)[0]
        both_front = (forces[:, self._front_cfg.body_ids] > threshold).all(dim=1)
        no_rear = (forces[:, self._rear_cfg.body_ids] <= threshold).all(dim=1)
        no_shoulder = (forces[:, self._shoulder_cfg.body_ids] <= threshold).all(dim=1)
        holding = (
            (g_b[:, 1] > min_gy)
            & (z > min_z)
            & (z < max_z)
            & (z_knees_min > min_knee_z)
            & both_front
            & no_rear
            & no_shoulder
        )
        self._hold_steps += holding.float()
        return torch.zeros(env.num_envs, device=env.device)
