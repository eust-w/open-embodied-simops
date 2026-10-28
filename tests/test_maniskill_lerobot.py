import random

from embodied_simops.integrations.maniskill_lerobot import (
    _seed_policy_rng,
    _trajectory_names_in_lerobot_order,
)


def test_trajectory_names_match_maniskill_lerobot_hdf5_iteration_order():
    names = ["traj_2", "traj_10", "metadata", "traj_1", "traj_100", "traj_0"]

    assert _trajectory_names_in_lerobot_order(names) == [
        "traj_0",
        "traj_1",
        "traj_10",
        "traj_100",
        "traj_2",
    ]


def test_seed_policy_rng_makes_python_random_reproducible():
    _seed_policy_rng(20260608)
    first = random.random()

    _seed_policy_rng(20260608)
    second = random.random()

    assert second == first
