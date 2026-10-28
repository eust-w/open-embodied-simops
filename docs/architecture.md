# Architecture

Open Embodied SimOps is a private orchestrator, not a replacement for robotics
engines. Each pipeline stage invokes a real local component and the engine only
marks success after declared files or directories exist.

## Core Runtime

- `TaskConfig` validates the closed-loop dimensions: simulator, robot, scene,
  assets, task, sensors, randomization, data format, training strategy, and
  deployment targets.
- `SimOpsEngine` serializes runs with a filesystem lock under the state
  directory.
- `CommandAdapter` runs external commands in a per-run workspace with
  `SIMOPS_RUN_ID`, `SIMOPS_RUN_DIR`, `SIMOPS_STATE_DIR`, and `SIMOPS_STAGE_ID`.
- `DependencyCheckAdapter` verifies executables, Python modules, and required
  environment variables.
- `DeploymentExportAdapter` creates ROS 2 and LeRobot rollout interface files
  bound to a real policy artifact hash.

## Provenance

For every declared artifact the engine records:

- run id and stage id,
- artifact name, role, relative path, and absolute path,
- SHA-256 hash,
- byte size,
- source component URI, version, and license.

Records are written to both SQLite and `provenance/artifacts.jsonl` inside the
run directory.

## Integration Pattern

Use `adapter: command` for heavy open-source tools:

- scene/asset generation: Infinigen, ProcTHOR, EmbodiedGen, RoboCasa,
- simulation and data collection: Genesis World, ManiSkill, MuJoCo, Gazebo,
- data conversion: ManiSkill `convert_to_lerobot`, RoboCasa HDF5 converter,
- model training/evaluation: `lerobot-train`, `lerobot-eval`, robomimic,
- deployment: generated ROS 2 bridge and LeRobot `lerobot-record` policy rollout launcher.

If a dependency, environment variable, command, or output artifact is missing,
the run fails.
