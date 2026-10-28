from __future__ import annotations

import argparse
import json
import random
import shutil
from pathlib import Path


ENVIRONMENT_STATE_KEY = "observation.environment_state"


def add_environment_state(dataset_root: Path, trajectory_h5: Path, output_root: Path) -> None:
    import numpy as np
    import pyarrow as pa
    import pyarrow.parquet as pq

    states, names = _load_environment_states(trajectory_h5)
    if output_root.exists():
        shutil.rmtree(output_root)
    shutil.copytree(dataset_root, output_root)

    offset = 0
    parquet_paths = sorted(output_root.glob("data/chunk-*/file-*.parquet"))
    if not parquet_paths:
        raise SystemExit(f"no parquet files found under {output_root}/data")

    for parquet_path in parquet_paths:
        table = pq.read_table(parquet_path)
        rows = table.num_rows
        chunk = states[offset : offset + rows]
        if len(chunk) != rows:
            raise SystemExit(
                f"trajectory state rows do not match dataset rows at {parquet_path}: "
                f"needed {rows}, got {len(chunk)}"
            )
        if ENVIRONMENT_STATE_KEY in table.schema.names:
            table = table.remove_column(table.schema.get_field_index(ENVIRONMENT_STATE_KEY))
        table = table.append_column(
            ENVIRONMENT_STATE_KEY,
            pa.array(chunk.astype("float32").tolist(), type=pa.list_(pa.float32())),
        )
        pq.write_table(table, parquet_path)
        offset += rows

    if offset != len(states):
        raise SystemExit(f"unused trajectory state rows: dataset used {offset}, HDF5 had {len(states)}")

    _update_info(output_root / "meta/info.json", len(names), names)
    _update_stats(output_root / "meta/stats.json", states)


def select_latest_policy(training_dir: Path, output_dir: Path, manifest_path: Path | None = None) -> None:
    checkpoint_dirs = []
    for candidate in (training_dir / "checkpoints").glob("*/pretrained_model"):
        if candidate.is_dir():
            checkpoint_dirs.append(candidate)
    if not checkpoint_dirs:
        raise SystemExit(f"no pretrained_model checkpoints found under {training_dir}/checkpoints")

    latest = sorted(checkpoint_dirs, key=lambda path: path.parent.name)[-1]
    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.copytree(latest, output_dir)

    manifest = {
        "source_checkpoint": str(latest),
        "selected_policy": str(output_dir),
    }
    target_manifest = manifest_path or output_dir.parent / "final_policy_manifest.json"
    target_manifest.parent.mkdir(parents=True, exist_ok=True)
    target_manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def evaluate_policy(
    policy_path: Path,
    metrics_path: Path,
    episodes: int,
    max_steps: int,
    min_success_rate: float,
    seed: int,
    policy_type: str,
    trajectory_h5: Path | None = None,
) -> None:
    import gymnasium as gym
    import mani_skill.envs  # noqa: F401
    import numpy as np
    import torch
    from lerobot.policies.factory import make_pre_post_processors

    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    policy = _load_policy(policy_path, policy_type)
    policy.to("cuda")
    policy.eval()
    preprocessor, postprocessor = make_pre_post_processors(
        policy_cfg=policy.config,
        pretrained_path=str(policy_path),
    )

    env = gym.make(
        "PickCube-v1",
        obs_mode="state_dict",
        control_mode="pd_joint_pos",
        render_mode=None,
        sim_backend="cpu",
        max_episode_steps=max_steps,
    )

    episode_metrics = []
    success_count = 0
    trajectory_names = _evaluation_trajectory_names(trajectory_h5, episodes) if trajectory_h5 else []
    try:
        for episode_index in range(episodes):
            episode_seed = seed + episode_index
            _seed_policy_rng(episode_seed)
            policy.reset()
            obs, _ = env.reset(seed=episode_seed)
            trajectory_name = None
            if trajectory_h5:
                trajectory_name = trajectory_names[episode_index]
                _restore_h5_initial_state(env, trajectory_h5, trajectory_name)
                obs = env.unwrapped.get_obs()
            total_reward = 0.0
            success = False
            last_info = {}

            for step in range(1, max_steps + 1):
                batch = preprocessor(_policy_batch_from_obs(obs))
                with torch.no_grad():
                    policy_action = policy.select_action(batch)
                    action = postprocessor(policy_action).detach().cpu().numpy()[0]
                action = np.clip(action, env.action_space.low, env.action_space.high).astype(np.float32)
                obs, reward, terminated, truncated, info = env.step(action)
                total_reward += float(reward.item() if hasattr(reward, "item") else reward)
                last_info = _jsonable_info(info)

                if "success" in info:
                    value = info["success"]
                    success = bool(value.item() if hasattr(value, "item") else value)
                if _as_bool(terminated) or _as_bool(truncated):
                    break

            success_count += int(success)
            record = {
                "episode_index": episode_index,
                "seed": episode_seed,
                "steps": step,
                "success": success,
                "total_reward": total_reward,
                "last_info": last_info,
            }
            if trajectory_name:
                record["trajectory"] = trajectory_name
            episode_metrics.append(record)
    finally:
        env.close()

    success_rate = success_count / episodes if episodes else 0.0
    metrics = {
        "env_id": "PickCube-v1",
        "obs_mode": "state_dict",
        "control_mode": "pd_joint_pos",
        "episodes": episodes,
        "max_steps": max_steps,
        "success_count": success_count,
        "success_rate": success_rate,
        "min_success_rate": min_success_rate,
        "policy_type": policy_type,
        "policy_path": str(policy_path),
        "trajectory_h5": str(trajectory_h5) if trajectory_h5 else None,
        "evaluation_initialization": "hdf5_initial_state" if trajectory_h5 else "seed_reset",
        "episode_metrics": episode_metrics,
    }
    metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(metrics, indent=2, sort_keys=True))

    if success_rate < min_success_rate:
        raise SystemExit(
            f"success_rate {success_rate:.3f} is below required threshold {min_success_rate:.3f}"
        )


def evaluate_act_policy(
    policy_path: Path,
    metrics_path: Path,
    episodes: int,
    max_steps: int,
    min_success_rate: float,
    seed: int,
) -> None:
    evaluate_policy(
        policy_path=policy_path,
        metrics_path=metrics_path,
        episodes=episodes,
        max_steps=max_steps,
        min_success_rate=min_success_rate,
        seed=seed,
        policy_type="act",
    )


def _load_policy(policy_path: Path, policy_type: str):
    if policy_type == "act":
        from lerobot.policies.act.modeling_act import ACTPolicy

        return ACTPolicy.from_pretrained(policy_path)
    if policy_type == "diffusion":
        from lerobot.policies.diffusion.modeling_diffusion import DiffusionPolicy

        return DiffusionPolicy.from_pretrained(policy_path)
    if policy_type == "smolvla":
        from lerobot.policies.smolvla.modeling_smolvla import SmolVLAPolicy

        return SmolVLAPolicy.from_pretrained(policy_path)
    raise SystemExit(f"unsupported policy type: {policy_type}")


def _evaluation_trajectory_names(trajectory_h5: Path, episodes: int) -> list[str]:
    import h5py

    with h5py.File(trajectory_h5, "r") as handle:
        trajectory_names = _trajectory_names_in_lerobot_order(handle.keys())
    if len(trajectory_names) < episodes:
        raise SystemExit(
            f"trajectory file only has {len(trajectory_names)} trajectories, "
            f"but {episodes} evaluation episodes were requested"
        )
    return trajectory_names[:episodes]


def _restore_h5_initial_state(env, trajectory_h5: Path, trajectory_name: str) -> None:
    import h5py
    import torch

    with h5py.File(trajectory_h5, "r") as handle:
        group = handle[trajectory_name]
        state = {
            "actors": {
                name: torch.as_tensor(dataset[0:1], dtype=torch.float32)
                for name, dataset in group["env_states/actors"].items()
            },
            "articulations": {
                name: torch.as_tensor(dataset[0:1], dtype=torch.float32)
                for name, dataset in group["env_states/articulations"].items()
            },
        }
    env.unwrapped.set_state_dict(state)


def _load_environment_states(trajectory_h5: Path):
    import h5py
    import numpy as np

    states = []
    with h5py.File(trajectory_h5, "r") as handle:
        trajectory_names = _trajectory_names_in_lerobot_order(handle.keys())
        for trajectory_name in trajectory_names:
            group = handle[trajectory_name]
            length = group["actions"].shape[0]
            parts = [
                group["obs/agent/qpos"][:length].astype("float32"),
                group["obs/agent/qvel"][:length].astype("float32"),
                group["obs/extra/tcp_pose"][:length].astype("float32"),
                group["obs/extra/obj_pose"][:length].astype("float32"),
                group["obs/extra/goal_pos"][:length].astype("float32"),
                group["obs/extra/tcp_to_obj_pos"][:length].astype("float32"),
                group["obs/extra/obj_to_goal_pos"][:length].astype("float32"),
                group["obs/extra/is_grasped"][:length].astype("float32").reshape(length, 1),
            ]
            states.append(np.concatenate(parts, axis=1))

    if not states:
        raise SystemExit(f"no trajectories found in {trajectory_h5}")

    names = (
        _indexed_names("qpos", 9)
        + _indexed_names("qvel", 9)
        + _indexed_names("tcp_pose", 7)
        + _indexed_names("obj_pose", 7)
        + _indexed_names("goal_pos", 3)
        + _indexed_names("tcp_to_obj_pos", 3)
        + _indexed_names("obj_to_goal_pos", 3)
        + ["is_grasped"]
    )
    return np.concatenate(states, axis=0), names


def _update_info(info_path: Path, state_dim: int, names: list[str]) -> None:
    info = json.loads(info_path.read_text(encoding="utf-8"))
    state_feature = dict(info["features"]["observation.state"])
    state_feature["shape"] = [state_dim]
    state_feature["names"] = names
    info["features"][ENVIRONMENT_STATE_KEY] = state_feature
    info_path.write_text(json.dumps(info, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _update_stats(stats_path: Path, states) -> None:
    import numpy as np

    values = states.astype("float64")
    stats = json.loads(stats_path.read_text(encoding="utf-8"))
    stats[ENVIRONMENT_STATE_KEY] = {
        "count": [int(values.shape[0])],
        "max": np.max(values, axis=0).tolist(),
        "mean": np.mean(values, axis=0).tolist(),
        "min": np.min(values, axis=0).tolist(),
        "std": np.std(values, axis=0).tolist(),
    }
    stats_path.write_text(json.dumps(stats, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _policy_batch_from_obs(obs):
    import torch

    qpos = _tensor(obs["agent"]["qpos"])
    qvel = _tensor(obs["agent"]["qvel"])
    extra = obs["extra"]
    environment_state = torch.cat(
        [
            qpos,
            qvel,
            _tensor(extra["tcp_pose"]),
            _tensor(extra["obj_pose"]),
            _tensor(extra["goal_pos"]),
            _tensor(extra["tcp_to_obj_pos"]),
            _tensor(extra["obj_to_goal_pos"]),
            _tensor(extra["is_grasped"]).to(dtype=torch.float32).reshape(qpos.shape[0], 1),
        ],
        dim=1,
    )
    return {
        "observation.state": qpos.to(dtype=torch.float32).cpu(),
        ENVIRONMENT_STATE_KEY: environment_state.to(dtype=torch.float32).cpu(),
    }


def _tensor(value):
    import torch

    if isinstance(value, torch.Tensor):
        tensor = value
    else:
        tensor = torch.as_tensor(value)
    if tensor.ndim == 1:
        tensor = tensor.unsqueeze(0)
    return tensor


def _jsonable_info(info: dict) -> dict:
    output = {}
    for key, value in info.items():
        if hasattr(value, "item"):
            output[key] = value.item()
        elif hasattr(value, "detach"):
            output[key] = value.detach().cpu().tolist()
        else:
            output[key] = value
    return output


def _as_bool(value) -> bool:
    if hasattr(value, "item"):
        return bool(value.item())
    return bool(value)


def _indexed_names(prefix: str, count: int) -> list[str]:
    return [f"{prefix}_{index}" for index in range(count)]


def _trajectory_names_in_lerobot_order(names) -> list[str]:
    # ManiSkill's LeRobot converter iterates HDF5 trajectory groups in h5py's
    # key order, which is lexicographic ("traj_0", "traj_1", "traj_10", ...).
    # Keep appended environment_state rows in that same order so every state row
    # stays aligned with the converted observation/action rows.
    return sorted(name for name in names if name.startswith("traj_"))


def _seed_policy_rng(seed: int) -> None:
    random.seed(seed)

    try:
        import numpy as np

        np.random.seed(seed)
    except ModuleNotFoundError:
        pass

    try:
        import torch

        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    except ModuleNotFoundError:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="ManiSkill to LeRobot production helpers")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add-environment-state")
    add_parser.add_argument("--dataset-root", type=Path, required=True)
    add_parser.add_argument("--trajectory-h5", type=Path, required=True)
    add_parser.add_argument("--output-root", type=Path, required=True)

    select_parser = subparsers.add_parser("select-latest-policy")
    select_parser.add_argument("--training-dir", type=Path, required=True)
    select_parser.add_argument("--output-dir", type=Path, required=True)
    select_parser.add_argument("--manifest-path", type=Path)

    eval_parser = subparsers.add_parser("evaluate-act")
    eval_parser.add_argument("--policy-path", type=Path, required=True)
    eval_parser.add_argument("--metrics-path", type=Path, required=True)
    eval_parser.add_argument("--episodes", type=int, required=True)
    eval_parser.add_argument("--max-steps", type=int, required=True)
    eval_parser.add_argument("--min-success-rate", type=float, required=True)
    eval_parser.add_argument("--seed", type=int, required=True)

    generic_eval_parser = subparsers.add_parser("evaluate-policy")
    generic_eval_parser.add_argument("--policy-type", choices=["act", "diffusion", "smolvla"], required=True)
    generic_eval_parser.add_argument("--policy-path", type=Path, required=True)
    generic_eval_parser.add_argument("--metrics-path", type=Path, required=True)
    generic_eval_parser.add_argument("--episodes", type=int, required=True)
    generic_eval_parser.add_argument("--max-steps", type=int, required=True)
    generic_eval_parser.add_argument("--min-success-rate", type=float, required=True)
    generic_eval_parser.add_argument("--seed", type=int, required=True)
    generic_eval_parser.add_argument("--trajectory-h5", type=Path)

    args = parser.parse_args()
    if args.command == "add-environment-state":
        add_environment_state(args.dataset_root, args.trajectory_h5, args.output_root)
    elif args.command == "select-latest-policy":
        select_latest_policy(args.training_dir, args.output_dir, args.manifest_path)
    elif args.command == "evaluate-act":
        evaluate_act_policy(
            args.policy_path,
            args.metrics_path,
            episodes=args.episodes,
            max_steps=args.max_steps,
            min_success_rate=args.min_success_rate,
            seed=args.seed,
        )
    elif args.command == "evaluate-policy":
        evaluate_policy(
            args.policy_path,
            args.metrics_path,
            episodes=args.episodes,
            max_steps=args.max_steps,
            min_success_rate=args.min_success_rate,
            seed=args.seed,
            policy_type=args.policy_type,
            trajectory_h5=args.trajectory_h5,
        )


if __name__ == "__main__":
    main()
