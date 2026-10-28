from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Open Embodied SimOps dataset operations")
    subparsers = parser.add_subparsers(dest="command", required=True)
    merge = subparsers.add_parser("merge-lerobot")
    merge.add_argument("--output", required=True)
    merge.add_argument("datasets", nargs="+")
    args = parser.parse_args()

    if args.command == "merge-lerobot":
        merge_lerobot([Path(item) for item in args.datasets], Path(args.output))


def merge_lerobot(dataset_roots: list[Path], output_root: Path) -> None:
    if len(dataset_roots) < 2:
        raise SystemExit("merge_lerobot requires at least two datasets")
    for root in dataset_roots:
        if not (root / "meta" / "info.json").exists():
            raise SystemExit(f"not a LeRobot dataset: {root}")

    import pandas as pd

    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "data" / "chunk-000").mkdir(parents=True, exist_ok=True)
    (output_root / "meta").mkdir(parents=True, exist_ok=True)

    frames = []
    tasks = []
    frame_offset = 0
    episode_offset = 0
    for root in dataset_roots:
        for parquet_path in sorted((root / "data").rglob("*.parquet")):
            frame = pd.read_parquet(parquet_path)
            if "index" in frame.columns:
                frame["index"] = frame["index"] + frame_offset
            if "episode_index" in frame.columns:
                frame["episode_index"] = frame["episode_index"] + episode_offset
            frames.append(frame)
            frame_offset += len(frame)
            if "episode_index" in frame.columns and len(frame):
                episode_offset = max(episode_offset, int(frame["episode_index"].max()) + 1)
        task_path = root / "meta" / "tasks.parquet"
        if task_path.exists():
            task_frame = pd.read_parquet(task_path)
            if "task_index" in task_frame.columns and len(tasks):
                task_frame["task_index"] = task_frame["task_index"] + sum(len(item) for item in tasks)
            tasks.append(task_frame)

    if not frames:
        raise SystemExit("no parquet data files found")
    merged = pd.concat(frames, ignore_index=True)
    merged.to_parquet(output_root / "data" / "chunk-000" / "file-000.parquet", index=False)

    if tasks:
        pd.concat(tasks, ignore_index=True).drop_duplicates().to_parquet(output_root / "meta" / "tasks.parquet", index=False)

    info = json.loads((dataset_roots[0] / "meta" / "info.json").read_text(encoding="utf-8"))
    info["total_frames"] = int(len(merged))
    if "episode_index" in merged.columns and len(merged):
        info["total_episodes"] = int(merged["episode_index"].nunique())
    info["data_files_size_in_mb"] = round(
        (output_root / "data" / "chunk-000" / "file-000.parquet").stat().st_size / (1024 * 1024),
        6,
    )
    info["source_datasets"] = [str(root) for root in dataset_roots]
    (output_root / "meta" / "info.json").write_text(json.dumps(info, indent=2, sort_keys=True), encoding="utf-8")

    stats_path = dataset_roots[0] / "meta" / "stats.json"
    if stats_path.exists():
        shutil.copy2(stats_path, output_root / "meta" / "stats.json")
    print(json.dumps({"status": "succeeded", "output_path": str(output_root), "total_frames": int(len(merged))}))


if __name__ == "__main__":
    main()
