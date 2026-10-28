import pytest

from embodied_simops.config import ConfigError, load_task_config


def test_task_config_requires_complete_closed_loop_dimensions(tmp_path):
    config_path = tmp_path / "task.yaml"
    config_path.write_text(
        """
schema_version: simops/v1
name: missing-stack-fields
components:
  genesis_world:
    kind: simulator
    source:
      uri: https://github.com/Genesis-Embodied-AI/genesis-world
      version: "0.2.1"
      license: Apache-2.0
pipeline: []
stack:
  simulator:
    component: genesis_world
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError) as excinfo:
        load_task_config(config_path)

    message = str(excinfo.value)
    assert "stack.robot" in message
    assert "stack.scene" in message
    assert "stack.training_strategy" in message
    assert "stack.deployment_targets" in message


def test_task_config_rejects_components_without_source_version_or_license(tmp_path):
    config_path = tmp_path / "task.yaml"
    config_path.write_text(
        """
schema_version: simops/v1
name: untraceable-component
components:
  robocasa:
    kind: scene_dataset
    source:
      uri: https://github.com/robocasa/robocasa
      version: "1.0.1"
pipeline: []
stack:
  simulator:
    component: genesis_world
  robot:
    name: panda
  scene:
    generator: robocasa
  assets:
    - component: robocasa
  task:
    id: PickPlaceDrawerToCounter
  sensors:
    cameras: []
  randomization:
    seed: 7
  data_format:
    name: lerobot
  training_strategy:
    policy: act
  deployment_targets:
    - lerobot_rollout
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="components.robocasa.source.license"):
        load_task_config(config_path)
