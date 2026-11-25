# Copyright (c) 2026. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause

"""1:1 Real-Scale Petoi Bittle X handstand environment (IMU-deployable actor + max DR + knees off ground)."""

from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.assets.articulation import ArticulationCfg
from isaaclab.managers import EventTermCfg as EventTerm
from isaaclab.managers import ObservationGroupCfg as ObsGroup
from isaaclab.managers import ObservationTermCfg as ObsTerm
from isaaclab.managers import RewardTermCfg as RewTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.managers import TerminationTermCfg as DoneTerm
import isaaclab.sim as sim_utils
from isaaclab.utils import configclass, replace
from isaaclab.utils.noise import UniformNoiseCfg as Unoise
from isaaclab_physx.sim.schemas import PhysxArticulationCfg, PhysxRigidBodyCfg

from ... import mdp
from ...velocity_env_cfg import LocomotionVelocityRoughEnvCfg
from . import handstand_mdp

# True 1:1 physical Petoi Bittle X (~10.4 cm wheelbase, 0.271 kg, P1S servos ~350 deg/s & 20-40 ms lag)
BITTLE_REAL_CFG = ArticulationCfg(
    spawn=sim_utils.UsdFileCfg(
        usd_path="/home/robotics/isaac/bittle_asset_real/bittle.usd",
        activate_contact_sensors=True,
        rigid_props=PhysxRigidBodyCfg(
            disable_gravity=False,
            retain_accelerations=False,
            linear_damping=0.05,
            angular_damping=0.05,
            max_linear_velocity=10.0,
            max_angular_velocity=50.0,
            max_depenetration_velocity=1.0,
        ),
        articulation_props=PhysxArticulationCfg(
            enabled_self_collisions=False, solver_position_iteration_count=8, solver_velocity_iteration_count=1
        ),
    ),
    init_state=ArticulationCfg.InitialStateCfg(
        pos=(0.0, 0.0, 0.074),
        joint_pos={
            "left_.*_shoulder_joint": 0.0,
            "right_.*_shoulder_joint": 0.0,
            "left_.*_knee_joint": 0.4,
            "right_.*_knee_joint": -0.4,
        },
        joint_vel={".*": 0.0},
    ),
    soft_joint_pos_limit_factor=0.9,
    actuators={
        "legs": ImplicitActuatorCfg(
            joint_names_expr=[".*_shoulder_joint", ".*_knee_joint"],
            effort_limit=0.35,
            velocity_limit=6.1,
            stiffness=2.0,
            damping=0.08,
        ),
    },
)


@configclass
class HandstandCommandsCfg:
    """No velocity commands needed for handstand balancing."""

    base_velocity = mdp.NullCommandCfg()


@configclass
class HandstandObservationsCfg:
    """Asymmetric Actor-Critic: Actor uses ONLY IMU + action history (100% real-robot deployable)."""

    @configclass
    class PolicyCfg(ObsGroup):
        base_ang_vel = ObsTerm(func=mdp.base_ang_vel, noise=Unoise(n_min=-0.35, n_max=0.35))
        projected_gravity = ObsTerm(func=mdp.projected_gravity, noise=Unoise(n_min=-0.08, n_max=0.08))
        actions = ObsTerm(func=mdp.last_action)

        def __post_init__(self):
            self.enable_corruption = True
            self.concatenate_terms = True
            self.history_length = 4
            self.flatten_history_dim = True

    @configclass
    class CriticCfg(ObsGroup):
        base_lin_vel = ObsTerm(func=mdp.base_lin_vel)
        base_ang_vel = ObsTerm(func=mdp.base_ang_vel)
        projected_gravity = ObsTerm(func=mdp.projected_gravity)
        joint_pos = ObsTerm(func=mdp.joint_pos_rel)
        joint_vel = ObsTerm(func=mdp.joint_vel_rel)
        actions = ObsTerm(func=mdp.last_action)

        def __post_init__(self):
            self.enable_corruption = False
            self.concatenate_terms = True
            self.history_length = 2
            self.flatten_history_dim = True

    policy: PolicyCfg = PolicyCfg()
    critic: CriticCfg = CriticCfg()


@configclass
class HandstandEventsCfg:
    """Maximum domain randomization tuned for 1:1 real-scale Petoi Bittle X."""

    # 1. Surface friction & restitution (smooth wood to rubber mat)
    physics_material = EventTerm(
        func=mdp.randomize_rigid_body_material,
        mode="startup",
        params={
            "asset_cfg": SceneEntityCfg("robot", body_names=".*"),
            "static_friction_range": (0.25, 1.6),
            "dynamic_friction_range": (0.2, 1.4),
            "restitution_range": (0.0, 0.2),
            "num_buckets": 64,
        },
    )

    # 2. Mass randomization on torso and leg links
    add_base_mass = EventTerm(
        func=mdp.randomize_rigid_body_mass,
        mode="startup",
        params={
            "asset_cfg": SceneEntityCfg("robot", body_names="base_frame_link"),
            "mass_distribution_params": (0.8, 1.3),
            "operation": "scale",
            "distribution": "log_uniform",
        },
    )
    randomize_leg_mass = EventTerm(
        func=mdp.randomize_rigid_body_mass,
        mode="startup",
        params={
            "asset_cfg": SceneEntityCfg("robot", body_names=[".*_shoulder_link", ".*_knee_link"]),
            "mass_distribution_params": (0.8, 1.3),
            "operation": "scale",
            "distribution": "log_uniform",
        },
    )

    # 3. Real-scale Center of Mass offset on base_frame_link (±8-10 mm)
    base_com = EventTerm(
        func=mdp.randomize_rigid_body_com,
        mode="startup",
        params={
            "asset_cfg": SceneEntityCfg("robot", body_names="base_frame_link"),
            "com_range": {"x": (-0.008, 0.008), "y": (-0.010, 0.010), "z": (-0.005, 0.005)},
        },
    )

    # 4. Rigid body inertia randomization
    body_inertia = EventTerm(
        func=mdp.randomize_rigid_body_inertia,
        mode="startup",
        params={
            "asset_cfg": SceneEntityCfg("robot", body_names=".*"),
            "inertia_distribution_params": (0.8, 1.3),
            "operation": "scale",
            "distribution": "uniform",
            "diagonal_only": True,
        },
    )

    # 5. Actuator stiffness & damping randomization
    actuator_gains = EventTerm(
        func=mdp.randomize_actuator_gains,
        mode="startup",
        params={
            "asset_cfg": SceneEntityCfg("robot", joint_names=".*"),
            "stiffness_distribution_params": (0.65, 1.45),
            "damping_distribution_params": (0.6, 1.6),
            "operation": "scale",
            "distribution": "uniform",
        },
    )

    # 6. Joint friction & real-scale geared-servo armature randomization (prevents explicit PD ringing)
    joint_params = EventTerm(
        func=mdp.randomize_joint_parameters,
        mode="startup",
        params={
            "asset_cfg": SceneEntityCfg("robot", joint_names=".*"),
            "friction_distribution_params": (0.0, 0.015),
            "armature_distribution_params": (0.0015, 0.004),
            "operation": "abs",
            "distribution": "uniform",
        },
    )

    # 7. Per-world gravity perturbations (tilted surface / ±8% effective g)
    gravity_rand = EventTerm(
        func=mdp.randomize_physics_scene_gravity,
        mode="reset",
        params={
            "gravity_distribution_params": ([-0.5, -0.5, -0.8], [0.5, 0.5, 0.8]),
            "operation": "add",
            "distribution": "uniform",
        },
    )

    # 8. Persistent per-episode disturbance wrench on 0.27 kg torso
    base_external_force_torque = EventTerm(
        func=mdp.apply_external_force_torque,
        mode="reset",
        params={
            "asset_cfg": SceneEntityCfg("robot", body_names="base_frame_link"),
            "force_range": (-0.12, 0.12),
            "torque_range": (-0.010, 0.010),
        },
    )

    # 9. Initial pose & velocity randomization (1:1 scale)
    reset_base = EventTerm(
        func=mdp.reset_root_state_uniform,
        mode="reset",
        params={
            "pose_range": {
                "x": (-0.05, 0.05),
                "y": (-0.05, 0.05),
                "yaw": (-3.14, 3.14),
                "roll": (-0.12, 0.12),
                "pitch": (-0.20, 0.20),
            },
            "velocity_range": {
                "x": (-0.10, 0.10),
                "y": (-0.10, 0.10),
                "z": (-0.05, 0.05),
                "roll": (-0.25, 0.25),
                "pitch": (-0.25, 0.25),
                "yaw": (-0.25, 0.25),
            },
        },
    )

    # 10. Initial joint angle & velocity randomization
    reset_robot_joints = EventTerm(
        func=mdp.reset_joints_by_offset,
        mode="reset",
        params={
            "position_range": (-0.25, 0.25),
            "velocity_range": (-0.5, 0.5),
        },
    )

    # 11. In-episode random velocity impulse pushes (real-scale)
    push_robot = EventTerm(
        func=mdp.push_by_setting_velocity,
        mode="interval",
        interval_range_s=(3.0, 6.0),
        params={
            "velocity_range": {
                "x": (-0.12, 0.12),
                "y": (-0.12, 0.12),
                "z": (-0.05, 0.05),
                "roll": (-0.30, 0.30),
                "pitch": (-0.30, 0.30),
                "yaw": (-0.30, 0.30),
            }
        },
    )


@configclass
class HandstandRewardsCfg:
    """Reward terms driving 1:1 Bittle into a vertical paw-tip handstand with knees off the ground."""

    handstand_orientation = RewTerm(
        func=handstand_mdp.handstand_orientation_reward,
        weight=8.0,
        params={"std": 0.22},
    )
    handstand_height = RewTerm(
        func=handstand_mdp.handstand_height_reward,
        weight=3.5,
        params={"target_height": 0.100, "min_height": 0.055, "std": 0.025},
    )
    rear_above_base = RewTerm(
        func=handstand_mdp.rear_above_base_reward,
        weight=3.0,
        params={
            "min_rel_z": -0.025,
            "target_rel_z": 0.055,
            "asset_cfg": SceneEntityCfg("robot", body_names=".*_back_knee_link"),
        },
    )
    front_knees_elevated = RewTerm(
        func=handstand_mdp.front_knees_elevated_reward,
        weight=4.0,
        params={
            "min_z": 0.015,
            "target_z": 0.045,
            "asset_cfg": SceneEntityCfg("robot", body_names=".*_front_knee_link"),
        },
    )
    front_knees_low_penalty = RewTerm(
        func=handstand_mdp.front_knees_low_penalty,
        weight=-8.0,
        params={
            "safe_z": 0.030,
            "asset_cfg": SceneEntityCfg("robot", body_names=".*_front_knee_link"),
        },
    )
    front_feet_support = RewTerm(
        func=handstand_mdp.front_feet_support_reward,
        weight=3.0,
        params={
            "front_sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_front_knee_link"),
            "rear_sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_back_knee_link"),
            "shoulder_sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_shoulder_link"),
            "threshold": 0.02,
        },
    )
    handstand_hold = RewTerm(
        func=handstand_mdp.handstand_hold_bonus,
        weight=15.0,
        params={
            "front_sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_front_knee_link"),
            "rear_sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_back_knee_link"),
            "shoulder_sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_shoulder_link"),
            "front_knee_cfg": SceneEntityCfg("robot", body_names=".*_front_knee_link"),
            "min_gy": 0.82,
            "min_z": 0.070,
            "max_z": 0.145,
            "min_knee_z": 0.030,
            "threshold": 0.02,
        },
    )
    jump_penalty = RewTerm(
        func=handstand_mdp.jump_height_penalty,
        weight=-10.0,
        params={"max_z": 0.14},
    )
    handstand_stability = RewTerm(
        func=handstand_mdp.handstand_stability_penalty,
        weight=-0.25,
        params={"min_gy": 0.75},
    )
    rear_contact_penalty = RewTerm(
        func=mdp.undesired_contacts,
        weight=-3.5,
        params={
            "sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_back_knee_link"),
            "threshold": 0.02,
        },
    )
    shoulder_contact_penalty = RewTerm(
        func=mdp.undesired_contacts,
        weight=-10.0,
        params={
            "sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_shoulder_link"),
            "threshold": 0.02,
        },
    )
    termination_penalty = RewTerm(func=mdp.is_terminated, weight=-30.0)
    dof_torques_l2 = RewTerm(func=mdp.joint_torques_l2, weight=-1.0e-3)
    dof_acc_l2 = RewTerm(func=mdp.joint_acc_l2, weight=-2.5e-7)
    action_rate_l2 = RewTerm(func=mdp.action_rate_l2, weight=-0.005)
    dof_pos_limits = RewTerm(func=mdp.joint_pos_limits, weight=-1.0)

    metrics = RewTerm(
        func=handstand_mdp.handstand_metrics,
        weight=0.0,
        params={
            "front_sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_front_knee_link"),
            "rear_sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_back_knee_link"),
            "shoulder_sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_shoulder_link"),
            "front_knee_cfg": SceneEntityCfg("robot", body_names=".*_front_knee_link"),
            "min_gy": 0.82,
            "min_z": 0.070,
            "max_z": 0.145,
            "min_knee_z": 0.030,
            "threshold": 0.02,
        },
    )


@configclass
class HandstandTerminationsCfg:
    """Terminate on timeout or torso/head ground contact."""

    time_out = DoneTerm(func=mdp.time_out, time_out=True)
    base_contact = DoneTerm(
        func=mdp.illegal_contact,
        params={"sensor_cfg": SceneEntityCfg("contact_forces", body_names="base_frame_link"), "threshold": 0.1},
    )


@configclass
class BittleHandstandEnvCfg(LocomotionVelocityRoughEnvCfg):
    """1:1 real-scale Petoi Bittle X handstand environment with max DR and IMU-only actor."""

    commands: HandstandCommandsCfg = HandstandCommandsCfg()
    observations: HandstandObservationsCfg = HandstandObservationsCfg()
    events: HandstandEventsCfg = HandstandEventsCfg()
    rewards: HandstandRewardsCfg = HandstandRewardsCfg()
    terminations: HandstandTerminationsCfg = HandstandTerminationsCfg()

    def __post_init__(self):
        super().__post_init__()

        # Flat terrain without height scanner, tighter env spacing for 10 cm robot
        self.scene.env_spacing = 0.8
        self.scene.terrain.terrain_type = "plane"
        self.scene.terrain.terrain_generator = None
        self.scene.height_scanner = None
        self.curriculum.terrain_levels = None

        # 1:1 real-scale robot asset
        self.scene.robot = replace(BITTLE_REAL_CFG, prim_path="{ENV_REGEX_NS}/Robot")

        # Joint control scale balanced for kick-up & paw-tip balance
        self.actions.joint_pos.scale = 0.4

        # Tune Newton MJWarp solver & contact stiffness for 1:1 0.271 kg Bittle
        self.sim.physics.newton_mjwarp.num_substeps = 4
        self.sim.physics.newton_mjwarp.default_shape_cfg.ke = 1200.0
        self.sim.physics.newton_mjwarp.default_shape_cfg.kd = 50.0
        self.sim.physics.newton_mjwarp.solver_cfg.njmax = 1000
        self.sim.physics.newton_mjwarp.solver_cfg.nconmax = 300
        self.sim.physics.newton_mjwarp.solver_cfg.iterations = 100
        self.sim.physics.newton_mjwarp.solver_cfg.ls_iterations = 50
