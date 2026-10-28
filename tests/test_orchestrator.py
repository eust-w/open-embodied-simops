import hashlib
import json
import subprocess
import sys

import pytest

from embodied_simops.config import load_task_config
from embodied_simops.orchestrator import PipelineError, SimOpsEngine


def _write_success_config(path):
    python = sys.executable
    path.write_text(
        f"""
schema_version: simops/v1
name: real-command-pipeline
runtime:
  max_parallel_jobs: 1
components:
  test_scene_source:
    kind: scene_asset
    source:
      uri: file://local-test-scene-generator
      version: "2026-06-08"
      license: MIT
  test_policy_source:
    kind: model
    source:
      uri: file://local-test-policy-trainer
      version: "2026-06-08"
      license: MIT
pipeline:
  - id: generate_scene
    adapter: command
    uses: [test_scene_source]
    command:
      - "{python}"
      - "-c"
      - "from pathlib import Path; Path('scene').mkdir(); Path('scene/kitchen.txt').write_text('kitchen scene', encoding='utf-8')"
    outputs:
      - name: kitchen_scene
        path: scene/kitchen.txt
        role: scene
  - id: train_policy
    adapter: command
    uses: [test_policy_source]
    command:
      - "{python}"
      - "-c"
      - "from pathlib import Path; assert Path('scene/kitchen.txt').read_text(encoding='utf-8') == 'kitchen scene'; Path('policy').mkdir(); Path('policy/checkpoint.pt').write_bytes(b'policy bytes')"
    outputs:
      - name: policy_checkpoint
        path: policy/checkpoint.pt
        role: model
  - id: export_deployment
    adapter: deployment_export
    uses: [test_policy_source]
    policy_artifact: policy_checkpoint
    output_dir: deployment
    ros2:
      package: simops_policy_bridge
      node: policy_rollout_node
      observation_topic: /observations
      action_topic: /actions
    lerobot:
      robot_type: test_arm
      policy_type: act
    outputs:
      - name: ros2_rollout_node
        path: deployment/ros2/policy_rollout_node.py
        role: deployment_interface
      - name: lerobot_rollout
        path: deployment/lerobot/rollout.py
        role: deployment_interface
stack:
  simulator:
    component: test_scene_source
  robot:
    name: panda
    embodiment: single_arm
  scene:
    generator: test_scene_source
    kind: kitchen
  assets:
    - component: test_scene_source
  task:
    id: PickPlaceDrawerToCounter
    language: open the drawer and place the object on the counter
  sensors:
    cameras:
      - name: wrist
        width: 320
        height: 240
    proprioception: true
  randomization:
    seed: 11
  data_format:
    name: lerobot
  training_strategy:
    policy: act
    device: cpu
  deployment_targets:
    - ros2
    - lerobot_rollout
""",
        encoding="utf-8",
    )


def test_pipeline_runs_real_commands_and_records_artifact_hashes(tmp_path):
    config_path = tmp_path / "task.yaml"
    _write_success_config(config_path)

    engine = SimOpsEngine(tmp_path / "state")
    result = engine.run(load_task_config(config_path))

    assert result.status == "succeeded"
    assert [stage.id for stage in result.stages] == [
        "generate_scene",
        "train_policy",
        "export_deployment",
    ]

    policy_path = result.run_dir / "policy/checkpoint.pt"
    expected_hash = hashlib.sha256(policy_path.read_bytes()).hexdigest()
    policy_record = result.artifact("policy_checkpoint")
    assert policy_record.sha256 == expected_hash
    assert policy_record.source_components[0].source.license == "MIT"

    ledger = result.run_dir / "provenance" / "artifacts.jsonl"
    records = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert {record["name"] for record in records} >= {
        "kitchen_scene",
        "policy_checkpoint",
        "ros2_rollout_node",
        "lerobot_rollout",
    }
    assert all(record["sha256"] for record in records)

    rollout_script = (result.run_dir / "deployment/lerobot/rollout.py").read_text(encoding="utf-8")
    assert "lerobot-record" in rollout_script
    assert "--policy.pretrained_path=" in rollout_script
    assert "lerobot-rollout" not in rollout_script


def test_pipeline_fails_when_command_does_not_create_declared_output(tmp_path):
    python = sys.executable
    config_path = tmp_path / "bad.yaml"
    config_path.write_text(
        f"""
schema_version: simops/v1
name: missing-output
components:
  generator:
    kind: scene_asset
    source:
      uri: file://generator
      version: "1"
      license: MIT
pipeline:
  - id: generate_scene
    adapter: command
    uses: [generator]
    command: ["{python}", "-c", "print('completed without artifact')"]
    outputs:
      - name: scene
        path: scene/missing.usd
        role: scene
stack:
  simulator:
    component: generator
  robot:
    name: panda
  scene:
    generator: generator
  assets:
    - component: generator
  task:
    id: OpenDrawer
  sensors:
    cameras: []
  randomization:
    seed: 1
  data_format:
    name: lerobot
  training_strategy:
    policy: act
  deployment_targets:
    - lerobot_rollout
""",
        encoding="utf-8",
    )

    engine = SimOpsEngine(tmp_path / "state")
    with pytest.raises(PipelineError, match="declared output was not created"):
        engine.run(load_task_config(config_path))


def test_pipeline_fails_when_required_environment_template_is_missing(tmp_path):
    python = sys.executable
    config_path = tmp_path / "missing-env.yaml"
    config_path.write_text(
        f"""
schema_version: simops/v1
name: missing-env
components:
  generator:
    kind: scene_asset
    source:
      uri: file://generator
      version: "1"
      license: MIT
pipeline:
  - id: generate_scene
    adapter: command
    uses: [generator]
    command: ["{python}", "-c", "print('${{env:SIMOPS_REQUIRED_DATASET}}')"]
stack:
  simulator:
    component: generator
  robot:
    name: panda
  scene:
    generator: generator
  assets:
    - component: generator
  task:
    id: OpenDrawer
  sensors:
    cameras: []
  randomization:
    seed: 1
  data_format:
    name: lerobot
  training_strategy:
    policy: act
  deployment_targets:
    - lerobot_rollout
""",
        encoding="utf-8",
    )

    engine = SimOpsEngine(tmp_path / "state")
    with pytest.raises(PipelineError, match="missing environment variable SIMOPS_REQUIRED_DATASET"):
        engine.run(load_task_config(config_path))


def test_command_adapter_runs_python_when_service_path_is_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", "")
    config_path = tmp_path / "task.yaml"
    config_path.write_text(
        """
schema_version: simops/v1
name: empty-path-python-command
components:
  runtime:
    kind: runtime
    source:
      uri: file://runtime
      version: "1"
      license: MIT
pipeline:
  - id: verify_python
    adapter: command
    uses: [runtime]
    command:
      - python
      - -c
      - "from pathlib import Path; import embodied_simops; Path('runtime').mkdir(); Path('runtime/version.txt').write_text(embodied_simops.__version__, encoding='utf-8')"
    outputs:
      - name: runtime_marker
        path: runtime/version.txt
        role: runtime_check
stack:
  simulator:
    component: runtime
  robot:
    name: panda
  scene:
    generator: runtime
  assets:
    - component: runtime
  task:
    id: RuntimeCheck
  sensors:
    cameras: []
  randomization:
    seed: 1
  data_format:
    name: lerobot
  training_strategy:
    policy: act
  deployment_targets:
    - lerobot_rollout
""",
        encoding="utf-8",
    )

    result = SimOpsEngine(tmp_path / "state").run(load_task_config(config_path))

    assert result.status == "succeeded"
    assert result.artifact("runtime_marker").sha256


def test_cli_validate_reports_valid_configuration(tmp_path):
    config_path = tmp_path / "task.yaml"
    _write_success_config(config_path)

    completed = subprocess.run(
        [sys.executable, "-m", "embodied_simops.cli", "validate", str(config_path)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "valid" in completed.stdout


def test_cli_run_executes_pipeline_and_returns_run_id(tmp_path):
    config_path = tmp_path / "task.yaml"
    _write_success_config(config_path)

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "embodied_simops.cli",
            "run",
            str(config_path),
            "--state-dir",
            str(tmp_path / "state"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["status"] == "succeeded"
    assert payload["run_id"]
