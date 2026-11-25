# Copyright (c) 2026. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause

"""Configuration for the Petoi Bittle quadruped velocity-tracking environment on flat terrain."""

from isaaclab.utils import configclass

from .rough_env_cfg import BittleRoughEnvCfg


@configclass
class BittleFlatEnvCfg(BittleRoughEnvCfg):
    """Configuration for the Petoi Bittle velocity-tracking environment on flat terrain."""

    def __post_init__(self):
        super().__post_init__()

        # scene
        self.scene.terrain.terrain_type = "plane"
        self.scene.terrain.terrain_generator = None
        self.scene.height_scanner = None

        # observations
        self.observations.policy.height_scan = None

        # rewards
        self.rewards.flat_orientation_l2.weight = -2.5
        self.rewards.feet_air_time.weight = 0.25
        self.rewards.base_height_l2.params["sensor_cfg"] = None

        # curriculum
        self.curriculum.terrain_levels = None
