# Copyright (c) 2026. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause

"""Configuration for the Petoi Bittle quadruped velocity-tracking environment on rough terrain."""

from isaaclab.managers import RewardTermCfg as RewTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.utils import configclass, replace
import isaaclab.sim as sim_utils
from isaaclab.assets.articulation import ArticulationCfg
from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab_physx.sim.schemas import PhysxArticulationCfg, PhysxRigidBodyCfg

from ... import mdp
from ...velocity_env_cfg import LocomotionVelocityRoughEnvCfg, RewardsCfg

_BITTLE_STANDING_HEIGHT = 0.58

BITTLE_CFG = ArticulationCfg(
    spawn=sim_utils.UsdFileCfg(
        usd_path="/home/robotics/isaac/bittle_asset/bittle.usd",
        activate_contact_sensors=True,
        rigid_props=PhysxRigidBodyCfg(
            disable_gravity=False,
            retain_accelerations=False,
            linear_damping=0.0,
            angular_damping=0.0,
            max_linear_velocity=1000.0,
            max_angular_velocity=1000.0,
            max_depenetration_velocity=1.0,
        ),
        articulation_props=PhysxArticulationCfg(
            enabled_self_collisions=False, solver_position_iteration_count=4, solver_velocity_iteration_count=0
        ),
    ),
    init_state=ArticulationCfg.InitialStateCfg(
        pos=(0.0, 0.0, 0.62),
        joint_pos={
            ".*_shoulder_joint": 0.0,
            ".*_knee_joint": 0.2,
        },
        joint_vel={".*": 0.0},
    ),
    soft_joint_pos_limit_factor=0.9,
    actuators={
        "legs": ImplicitActuatorCfg(
            joint_names_expr=[".*_shoulder_joint", ".*_knee_joint"],
            effort_limit=15.0,
            velocity_limit=10.0,
            stiffness=25.0,
            damping=1.0,
        ),
    },
)


@configclass
class BittleRewards(RewardsCfg):
    """Adds a base-height penalty on top of shared velocity rewards."""

    base_height_l2 = RewTerm(
        func=mdp.base_height_l2,
        weight=-15.0,
        params={"target_height": _BITTLE_STANDING_HEIGHT},
    )


@configclass
class BittleRoughEnvCfg(LocomotionVelocityRoughEnvCfg):
    """Configuration for Bittle velocity-tracking environment on rough terrain."""

    rewards: BittleRewards = BittleRewards()

    def __post_init__(self):
        super().__post_init__()

        # scene
        self.scene.robot = replace(BITTLE_CFG, prim_path="{ENV_REGEX_NS}/Robot")
        self.scene.height_scanner.prim_path = "{ENV_REGEX_NS}/Robot/base_frame_link"

        # scale down terrains to match Bittle's size
        terrains = self.scene.terrain.terrain_generator.sub_terrains
        terrains["boxes"].grid_height_range = (0.015, 0.06)
        terrains["random_rough"].noise_range = (0.01, 0.04)
        terrains["random_rough"].noise_step = 0.01
        terrains["pyramid_stairs"].step_height_range = (0.015, 0.06)
        terrains["pyramid_stairs_inv"].step_height_range = (0.015, 0.06)

        # events (domain randomization references base_frame_link)
        self.events.add_base_mass.params["asset_cfg"].body_names = "base_frame_link"
        self.events.base_com.params["asset_cfg"].body_names = "base_frame_link"
        self.events.base_external_force_torque.params["asset_cfg"].body_names = "base_frame_link"

        # actions
        self.actions.joint_pos.scale = 0.25

        # rewards
        self.rewards.feet_air_time.params["sensor_cfg"].body_names = ".*_knee_link"
        self.rewards.feet_air_time.weight = 0.01
        self.rewards.undesired_contacts = None
        self.rewards.dof_torques_l2.weight = -0.0002
        self.rewards.track_lin_vel_xy_exp.weight = 1.5
        self.rewards.track_ang_vel_z_exp.weight = 0.75
        self.rewards.dof_acc_l2.weight = -2.5e-7
        self.rewards.base_height_l2.weight = -20.0
        self.rewards.base_height_l2.params["sensor_cfg"] = SceneEntityCfg("height_scanner")
        self.rewards.action_rate_l2.weight = -0.005

        # terminations
        self.terminations.base_contact.params["sensor_cfg"].body_names = "base_frame_link"
