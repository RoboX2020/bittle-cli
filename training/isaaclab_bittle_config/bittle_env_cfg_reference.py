# Copyright (c) 2026. All rights reserved.
# Custom Bittle Quadruped Locomotion Environment Configuration Reference
# Tuning reward terms, physics constraints, and command velocities

from isaaclab.managers import RewardTermCfg as RewTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.utils import configclass
import isaaclab_tasks.core.velocity.mdp as mdp
from isaaclab_tasks.core.velocity.velocity_env_cfg import RewardsCfg

_BITTLE_STANDING_HEIGHT = 0.58


@configclass
class CustomBittleRewards(RewardsCfg):
    """Custom reward terms for tuning Bittle quadruped locomotion."""

    # Termination penalty (falling or colliding base with ground)
    termination_penalty = RewTerm(func=mdp.is_terminated, weight=-200.0)

    # Velocity tracking (XY linear command and yaw angular rate)
    track_lin_vel_xy_exp = RewTerm(
        func=mdp.track_lin_vel_xy_yaw_frame_exp,
        weight=1.5,
        params={"command_name": "base_velocity", "std": 0.5},
    )
    track_ang_vel_z_exp = RewTerm(
        func=mdp.track_ang_vel_z_world_exp,
        weight=0.75,
        params={"command_name": "base_velocity", "std": 0.5},
    )

    # Base stability & orientation penalties
    lin_vel_z_l2 = RewTerm(func=mdp.lin_vel_z_l2, weight=-2.0)
    ang_vel_xy_l2 = RewTerm(func=mdp.ang_vel_xy_l2, weight=-0.05)
    flat_orientation_l2 = RewTerm(func=mdp.flat_orientation_l2, weight=-2.5)

    # Energy and action smoothness penalties
    dof_torques_l2 = RewTerm(func=mdp.joint_torques_l2, weight=-0.0002)
    dof_acc_l2 = RewTerm(func=mdp.joint_acc_l2, weight=-2.5e-7)
    action_rate_l2 = RewTerm(func=mdp.action_rate_l2, weight=-0.005)

    # Joint limit penalty
    dof_pos_limits = RewTerm(func=mdp.joint_pos_limits, weight=0.0)

    # Standing base height penalty
    base_height_l2 = RewTerm(
        func=mdp.base_height_l2,
        weight=-20.0,
        params={"target_height": _BITTLE_STANDING_HEIGHT},
    )

    # Gait & foot contact clearance
    feet_air_time = RewTerm(
        func=mdp.feet_air_time_positive_biped,
        weight=0.25,
        params={
            "command_name": "base_velocity",
            "sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_knee_link"),
            "threshold": 0.1,
        },
    )
