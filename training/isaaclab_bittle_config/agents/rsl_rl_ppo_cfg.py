# Copyright (c) 2026. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause

from isaaclab.utils import configclass
from isaaclab_rl.rsl_rl import RslRlMLPModelCfg, RslRlOnPolicyRunnerCfg, RslRlPpoAlgorithmCfg


@configclass
class BittleRoughPPORunnerCfg(RslRlOnPolicyRunnerCfg):
    num_steps_per_env = 24
    max_iterations = 1500
    save_interval = 50
    experiment_name = "bittle_rough"
    obs_groups = {"actor": ["policy"], "critic": ["policy"]}
    actor = RslRlMLPModelCfg(
        hidden_dims=[256, 128, 64],
        activation="elu",
        obs_normalization=False,
        distribution_cfg=RslRlMLPModelCfg.GaussianDistributionCfg(init_std=1.0),
    )
    critic = RslRlMLPModelCfg(
        hidden_dims=[256, 128, 64],
        activation="elu",
        obs_normalization=False,
    )
    algorithm = RslRlPpoAlgorithmCfg(
        value_loss_coef=1.0,
        use_clipped_value_loss=True,
        clip_param=0.2,
        entropy_coef=0.01,
        num_learning_epochs=5,
        num_mini_batches=4,
        learning_rate=1.0e-3,
        schedule="adaptive",
        gamma=0.99,
        lam=0.95,
        desired_kl=0.01,
        max_grad_norm=1.0,
    )


@configclass
class BittleFlatPPORunnerCfg(BittleRoughPPORunnerCfg):
    def __post_init__(self):
        super().__post_init__()

        self.max_iterations = 500
        self.experiment_name = "bittle_flat"
        self.actor.hidden_dims = [128, 128, 64]
        self.critic.hidden_dims = [128, 128, 64]


@configclass
class BittleHandstandPPORunnerCfg(BittleRoughPPORunnerCfg):
    def __post_init__(self):
        super().__post_init__()

        self.max_iterations = 50000
        self.save_interval = 100
        self.experiment_name = "bittle_handstand_real"
        self.obs_groups = {"actor": ["policy"], "critic": ["critic"]}
        self.clip_actions = 4.0
        self.actor.hidden_dims = [256, 128, 64]
        self.actor.obs_normalization = True
        self.actor.distribution_cfg = RslRlMLPModelCfg.GaussianDistributionCfg(
            init_std=0.8, std_range=(0.05, 1.5)
        )
        self.critic.hidden_dims = [256, 128, 64]
        self.critic.obs_normalization = True
        self.algorithm.entropy_coef = 0.002
