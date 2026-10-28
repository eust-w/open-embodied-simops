from __future__ import annotations

import fcntl
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from embodied_simops.config import ComponentRef, StageConfig, TaskConfig
from embodied_simops.provenance import ArtifactRecord, append_ledger, record_artifact
from embodied_simops.storage import SimOpsStore


class PipelineError(RuntimeError):
    """Raised when a pipeline cannot complete truthfully."""


@dataclass
class StageResult:
    id: str
    status: str
    adapter: str
    stdout_path: Path | None = None
    stderr_path: Path | None = None
    returncode: int | None = None
    error: str | None = None


@dataclass
class RunResult:
    run_id: str
    status: str
    run_dir: Path
    stages: list[StageResult] = field(default_factory=list)
    artifacts: list[ArtifactRecord] = field(default_factory=list)

    def artifact(self, name: str) -> ArtifactRecord:
        for artifact in self.artifacts:
            if artifact.name == name:
                return artifact
        raise KeyError(name)


@dataclass
class ExecutionContext:
    run_id: str
    run_dir: Path
    state_dir: Path
    config: TaskConfig
    artifacts: dict[str, ArtifactRecord] = field(default_factory=dict)


class SimOpsEngine:
    def __init__(self, state_dir: str | Path = ".simops"):
        self.store = SimOpsStore(state_dir)
        self.state_dir = self.store.state_dir
        self.lock_path = self.state_dir / "scheduler.lock"

    def run(self, config: TaskConfig) -> RunResult:
        if config.runtime.max_parallel_jobs != 1:
            raise PipelineError("MVP runtime is private and serial; set runtime.max_parallel_jobs to 1")

        with self._exclusive_lock():
            run_id = _new_run_id(config.name)
            run_dir = self.store.runs_dir / run_id
            run_dir.mkdir(parents=True, exist_ok=False)
            (run_dir / "logs").mkdir()
            (run_dir / "provenance").mkdir()
            _write_config_snapshot(run_dir, config)

            self.store.create_run(run_id, config.name, run_dir)
            context = ExecutionContext(run_id=run_id, run_dir=run_dir, state_dir=self.state_dir, config=config)
            result = RunResult(run_id=run_id, status="running", run_dir=run_dir)

            try:
                for stage in config.pipeline:
                    stage_result = self._run_stage(stage, context)
                    result.stages.append(stage_result)

                    source_components = [config.components[component_id] for component_id in stage.uses]
                    for output in stage.outputs:
                        artifact_path = run_dir / output.path
                        if not artifact_path.exists():
                            raise PipelineError(
                                f"{stage.id}: declared output was not created: {output.path}"
                            )
                        record = record_artifact(
                            run_id=run_id,
                            stage_id=stage.id,
                            run_dir=run_dir,
                            output=output,
                            source_components=source_components,
                        )
                        context.artifacts[record.name] = record
                        result.artifacts.append(record)
                        append_ledger(run_dir, record)
                        self.store.record_artifact(record)

                result.status = "succeeded"
                self.store.update_run(run_id, "succeeded")
                return result
            except Exception as exc:
                result.status = "failed"
                self.store.update_run(run_id, "failed", str(exc))
                if isinstance(exc, PipelineError):
                    raise
                raise PipelineError(str(exc)) from exc

    def _run_stage(self, stage: StageConfig, context: ExecutionContext) -> StageResult:
        self.store.record_stage(
            run_id=context.run_id,
            stage_id=stage.id,
            status="running",
            adapter=stage.adapter,
            stdout_path=None,
            stderr_path=None,
            returncode=None,
        )

        try:
            if stage.adapter == "command":
                result = CommandAdapter().run(stage, context)
            elif stage.adapter == "dependency_check":
                result = DependencyCheckAdapter().run(stage, context)
            elif stage.adapter == "deployment_export":
                result = DeploymentExportAdapter().run(stage, context)
            else:
                raise PipelineError(f"{stage.id}: unknown adapter {stage.adapter}")
        except Exception as exc:
            stage_result = StageResult(id=stage.id, status="failed", adapter=stage.adapter, error=str(exc))
            self.store.record_stage(
                run_id=context.run_id,
                stage_id=stage.id,
                status="failed",
                adapter=stage.adapter,
                stdout_path=None,
                stderr_path=None,
                returncode=None,
                error=str(exc),
            )
            raise

        self.store.record_stage(
            run_id=context.run_id,
            stage_id=stage.id,
            status=result.status,
            adapter=stage.adapter,
            stdout_path=result.stdout_path,
            stderr_path=result.stderr_path,
            returncode=result.returncode,
            error=result.error,
        )
        return result

    @contextmanager
    def _exclusive_lock(self) -> Iterator[None]:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("w", encoding="utf-8") as handle:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise PipelineError("another SimOps run is already active") from exc
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class CommandAdapter:
    def run(self, stage: StageConfig, context: ExecutionContext) -> StageResult:
        command = [render_template(value, context) for value in stage.command or []]
        cwd = context.run_dir / render_template(stage.cwd, context) if stage.cwd else context.run_dir
        cwd.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env["PATH"] = _command_path(env.get("PATH"))
        env.update(
            {
                "SIMOPS_RUN_ID": context.run_id,
                "SIMOPS_RUN_DIR": str(context.run_dir),
                "SIMOPS_STATE_DIR": str(context.state_dir),
                "SIMOPS_STAGE_ID": stage.id,
            }
        )
        env.update({key: render_template(value, context) for key, value in stage.env.items()})
        if command and command[0] in {"python", "python3"}:
            command[0] = sys.executable

        stdout_path = context.run_dir / "logs" / f"{stage.id}.stdout.log"
        stderr_path = context.run_dir / "logs" / f"{stage.id}.stderr.log"
        with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
            completed = subprocess.run(
                command,
                cwd=cwd,
                env=env,
                stdout=stdout,
                stderr=stderr,
                text=True,
                timeout=stage.timeout_seconds,
            )

        if completed.returncode != 0:
            raise PipelineError(
                f"{stage.id}: command failed with exit code {completed.returncode}; "
                f"see {stderr_path}"
            )

        return StageResult(
            id=stage.id,
            status="succeeded",
            adapter=stage.adapter,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            returncode=completed.returncode,
        )


class DependencyCheckAdapter:
    def run(self, stage: StageConfig, context: ExecutionContext) -> StageResult:
        missing: list[str] = []

        for executable in stage.executables:
            if shutil.which(render_template(executable, context)) is None:
                missing.append(f"executable:{executable}")

        for module_name in stage.python_modules:
            if importlib.util.find_spec(render_template(module_name, context)) is None:
                missing.append(f"python_module:{module_name}")

        for env_var in stage.env_vars:
            if not os.environ.get(env_var):
                missing.append(f"env:{env_var}")

        if missing:
            raise PipelineError(f"{stage.id}: missing required dependencies: {', '.join(missing)}")

        return StageResult(id=stage.id, status="succeeded", adapter=stage.adapter, returncode=0)


class DeploymentExportAdapter:
    def run(self, stage: StageConfig, context: ExecutionContext) -> StageResult:
        policy_path = self._resolve_policy_path(stage, context)
        if not policy_path.exists():
            raise PipelineError(f"{stage.id}: policy path does not exist: {policy_path}")

        output_dir = context.run_dir / render_template(stage.output_dir or "", context)
        ros2_dir = output_dir / "ros2"
        lerobot_dir = output_dir / "lerobot"
        ros2_dir.mkdir(parents=True, exist_ok=True)
        lerobot_dir.mkdir(parents=True, exist_ok=True)

        policy_record = context.artifacts.get(stage.policy_artifact or "")
        policy_hash = policy_record.sha256 if policy_record else _hash_existing_policy(policy_path)
        ros2_config = _render_data(stage.ros2, context)
        lerobot_config = _render_data(stage.lerobot, context)
        metadata = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "run_id": context.run_id,
            "stage_id": stage.id,
            "policy_path": str(policy_path),
            "policy_sha256": policy_hash,
            "ros2": ros2_config,
            "lerobot": lerobot_config,
        }

        (output_dir / "deployment_manifest.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        self._write_ros2_node(ros2_dir, stage, metadata)
        self._write_lerobot_rollout(lerobot_dir, stage, metadata)

        return StageResult(id=stage.id, status="succeeded", adapter=stage.adapter, returncode=0)

    def _resolve_policy_path(self, stage: StageConfig, context: ExecutionContext) -> Path:
        if stage.policy_artifact:
            try:
                return Path(context.artifacts[stage.policy_artifact].path)
            except KeyError as exc:
                raise PipelineError(f"{stage.id}: unknown policy_artifact {stage.policy_artifact}") from exc
        assert stage.policy_path is not None
        rendered = render_template(stage.policy_path, context)
        policy_path = Path(rendered)
        return policy_path if policy_path.is_absolute() else context.run_dir / policy_path

    def _write_ros2_node(self, ros2_dir: Path, stage: StageConfig, metadata: dict) -> None:
        ros2_config = metadata["ros2"]
        lerobot_config = metadata["lerobot"]
        package = ros2_config.get("package", "simops_policy_bridge")
        node = ros2_config.get("node", "policy_rollout_node")
        observation_topic = ros2_config.get("observation_topic", "/simops/observations")
        action_topic = ros2_config.get("action_topic", "/simops/actions")
        script = f'''#!/usr/bin/env python3
"""ROS 2 bridge generated by Open Embodied SimOps.

The node exposes a JSON-over-std_msgs/String interface. Replace the message
conversion functions with robot-specific message types when integrating with a
production controller.
"""

import json
import os
import subprocess

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

POLICY_PATH = {metadata["policy_path"]!r}
POLICY_SHA256 = {metadata["policy_sha256"]!r}
LEROBOT_ROBOT_TYPE = {lerobot_config.get("robot_type", "")!r}
LEROBOT_TASK = {lerobot_config.get("task", "")!r}


class PolicyRolloutNode(Node):
    def __init__(self):
        super().__init__({node!r})
        self.publisher = self.create_publisher(String, {action_topic!r}, 10)
        self.subscription = self.create_subscription(String, {observation_topic!r}, self.on_observation, 10)
        self.get_logger().info("SimOps policy bridge ready for " + POLICY_PATH)

    def on_observation(self, message):
        payload = json.loads(message.data)
        runner = os.environ.get("SIMOPS_POLICY_RUNNER")
        if not runner:
            raise RuntimeError("SIMOPS_POLICY_RUNNER must point to a robot-specific policy runner")
        completed = subprocess.run(
            [runner, "--policy-path", POLICY_PATH, "--observation-json", json.dumps(payload)],
            check=True,
            capture_output=True,
            text=True,
        )
        action = String()
        action.data = completed.stdout.strip()
        self.publisher.publish(action)


def main():
    rclpy.init()
    node_instance = PolicyRolloutNode()
    try:
        rclpy.spin(node_instance)
    finally:
        node_instance.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
'''
        target = ros2_dir / f"{node}.py"
        target.write_text(script, encoding="utf-8")
        target.chmod(0o755)
        (ros2_dir / "package.txt").write_text(
            f"Package: {package}\nNode: {node}\nObservation topic: {observation_topic}\nAction topic: {action_topic}\n",
            encoding="utf-8",
        )

    def _write_lerobot_rollout(self, lerobot_dir: Path, stage: StageConfig, metadata: dict) -> None:
        lerobot_config = metadata["lerobot"]
        robot_type = lerobot_config.get("robot_type", "")
        policy_type = lerobot_config.get("policy_type", "")
        task = lerobot_config.get("task", "")
        duration = int(lerobot_config.get("duration_seconds", 30))
        robot_port = lerobot_config.get("robot_port", "$SIMOPS_ROBOT_PORT")
        dataset_repo_id = lerobot_config.get("dataset_repo_id", f"simops/{metadata['run_id']}-rollout")
        script = f'''#!/usr/bin/env python3
"""LeRobot policy rollout recorder generated by Open Embodied SimOps."""

import argparse
import os
import subprocess

POLICY_PATH = {metadata["policy_path"]!r}
POLICY_SHA256 = {metadata["policy_sha256"]!r}
DEFAULT_ROBOT_TYPE = {robot_type!r}
DEFAULT_POLICY_TYPE = {policy_type!r}
DEFAULT_TASK = {task!r}
DEFAULT_DURATION = {duration!r}
DEFAULT_ROBOT_PORT = {robot_port!r}
DEFAULT_DATASET_REPO_ID = {dataset_repo_id!r}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--robot-type", default=DEFAULT_ROBOT_TYPE)
    parser.add_argument("--robot-port", default=os.path.expandvars(DEFAULT_ROBOT_PORT))
    parser.add_argument("--policy-type", default=DEFAULT_POLICY_TYPE)
    parser.add_argument("--task", default=DEFAULT_TASK)
    parser.add_argument("--duration", type=int, default=DEFAULT_DURATION)
    parser.add_argument("--dataset-repo-id", default=DEFAULT_DATASET_REPO_ID)
    parser.add_argument("--record-command", default=os.environ.get("SIMOPS_LEROBOT_RECORD", "lerobot-record"))
    parser.add_argument("--extra", nargs="*", default=[])
    args = parser.parse_args()

    if not args.robot_type:
        raise SystemExit("--robot-type is required")
    if not args.robot_port:
        raise SystemExit("--robot-port or SIMOPS_ROBOT_PORT is required")

    if not args.policy_type:
        raise SystemExit("--policy-type is required")
    if not args.dataset_repo_id:
        raise SystemExit("--dataset-repo-id is required")

    command = [
        args.record_command,
        f"--robot.type={{args.robot_type}}",
        f"--robot.port={{args.robot_port}}",
        f"--policy.type={{args.policy_type}}",
        f"--policy.pretrained_path={{POLICY_PATH}}",
        f"--dataset.repo_id={{args.dataset_repo_id}}",
        f"--dataset.single_task={{args.task}}",
        f"--dataset.num_episodes=1",
        f"--dataset.episode_time_s={{args.duration}}",
        "--dataset.push_to_hub=false",
    ] + args.extra
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
'''
        target = lerobot_dir / "rollout.py"
        target.write_text(script, encoding="utf-8")
        target.chmod(0o755)


TEMPLATE_PATTERN = re.compile(r"\$\{([^}]+)\}")


def render_template(value: str | None, context: ExecutionContext) -> str:
    if value is None:
        return ""

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key == "run_id":
            return context.run_id
        if key == "run_dir":
            return str(context.run_dir)
        if key == "state_dir":
            return str(context.state_dir)
        if key.startswith("env:"):
            env_name = key[4:]
            value = os.environ.get(env_name)
            if not value:
                raise PipelineError(f"missing environment variable {env_name}")
            return value
        if key.startswith("artifacts.") and key.endswith(".path"):
            artifact_name = key[len("artifacts.") : -len(".path")]
            return context.artifacts[artifact_name].path
        raise PipelineError(f"unknown template variable {key}")

    return TEMPLATE_PATTERN.sub(replace, value)


def _render_data(value: Any, context: ExecutionContext) -> Any:
    if isinstance(value, str):
        return render_template(value, context)
    if isinstance(value, list):
        return [_render_data(item, context) for item in value]
    if isinstance(value, dict):
        return {key: _render_data(item, context) for key, item in value.items()}
    return value


def _write_config_snapshot(run_dir: Path, config: TaskConfig) -> None:
    (run_dir / "task_config.json").write_text(
        json.dumps(config.model_dump(), indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _new_run_id(name: str) -> str:
    clean_name = re.sub(r"[^a-zA-Z0-9_.-]+", "-", name).strip("-").lower() or "run"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{clean_name}-{uuid.uuid4().hex[:8]}"


def _hash_existing_policy(path: Path) -> str:
    from embodied_simops.provenance import sha256_path

    digest, _ = sha256_path(path)
    return digest


def _command_path(existing_path: str | None) -> str:
    python_bin = str(Path(sys.executable).parent)
    path_parts = [python_bin]
    if existing_path:
        path_parts.append(existing_path)
    else:
        path_parts.append(os.defpath)
    return os.pathsep.join(path_parts)
