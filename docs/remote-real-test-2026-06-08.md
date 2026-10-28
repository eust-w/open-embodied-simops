# Remote Real Test Record - 2026-06-08

Historical record, not a current acceptance report. The host was unreachable
during the 2026-10-29 release audit; raw artifacts were not revalidated then.

Host: private GPU host (connection details withheld from the public repository).

Project path: `/opt/open-embodied-simops`

Service:

- systemd unit: `simops-api.service`
- listen address: `127.0.0.1:18080`
- health endpoint: `/health`

Hardware observed during the test:

- GPU: NVIDIA RTX5880-Ada-48Q
- VRAM: 49152 MiB
- Driver: 570.172.18
- CUDA runtime reported by driver: 12.8
- System memory: about 125 GiB

Runtime environments:

- `/opt/open-embodied-simops/.venv`
  - Open Embodied SimOps service and CLI
  - LeRobot 0.4.4
  - PyTorch 2.10.0+cu128
  - NumPy 2.x stack for LeRobot/Rerun/OpenCV
- `/opt/open-embodied-simops/.maniskill-mp-venv`
  - ManiSkill 3.0.1 motion planning data collection
  - NumPy 1.26.4 stack for `toppra`/Cython ABI compatibility
  - PyTorch 2.10.0+cu128

The two-venv split is intentional. ManiSkill motion planning currently pulls
native extensions that are not compatible with the NumPy 2.x stack used by the
current LeRobot install.

Real API/CLI checks:

- API workflow run:
  `20260608T145131Z-api-real-usage-command-env-41d7613d`
- API workflow run after deployment-export fix:
  `20260608T152908Z-api-real-usage-command-env-1b5ca933`
- CLI workflow run:
  `20260608T145150Z-api-real-usage-command-env-0790888b`
- Both completed through real command execution, artifact hashing, provenance
  ledger writing, and deployment interface export.

Final repository example run:

- run id: `20260608T152755Z-mvp-maniskill-lerobot-tabletop-pickcube-bee7b0c9`
- state dir: `/var/lib/open-embodied-simops/repo-example-real-run`
- run dir:
  `/var/lib/open-embodied-simops/repo-example-real-run/runs/20260608T152755Z-mvp-maniskill-lerobot-tabletop-pickcube-bee7b0c9`
- status: `succeeded`
- provenance artifacts: 8
- exported LeRobot interface: generated `rollout.py` calls the real LeRobot
  0.4.4 `lerobot-record` CLI with `--policy.pretrained_path`.

Real robotics pipeline run:

- run id: `20260608T152007Z-real-maniskill-lerobot-act-pickcube-5cd07a59`
- state dir: `/var/lib/open-embodied-simops/robotics-pipeline-run`
- run dir:
  `/var/lib/open-embodied-simops/robotics-pipeline-run/runs/20260608T152007Z-real-maniskill-lerobot-act-pickcube-5cd07a59`
- status: `succeeded`

Pipeline stages completed:

1. validated robotics Python environments
2. collected a ManiSkill `PickCube-v1` motion-planned trajectory
3. converted the trajectory to a LeRobot dataset
4. added ACT-compatible `observation.environment_state`
5. trained an ACT policy diagnostic checkpoint on CUDA
6. loaded the trained policy and rolled it out in ManiSkill
7. exported ROS 2 and LeRobot deployment interface files

Produced provenance artifacts:

- `robotics_envs`
- `maniskill_trajectory_h5`
- `maniskill_trajectory_json`
- `lerobot_raw_dataset`
- `lerobot_act_dataset`
- `act_policy`
- `sim_eval_metrics`
- `ros2_rollout_node`
- `lerobot_rollout`

Evaluation metrics from the diagnostic policy:

```json
{
  "env_id": "PickCube-v1",
  "obs_mode": "state_dict",
  "control_mode": "pd_joint_pos",
  "steps": 50,
  "success": false,
  "total_reward": 0.048781990102725103
}
```

The evaluation is a real simulation rollout of the trained checkpoint. The
`success: false` result came from an earlier diagnostic run and is not an
acceptance benchmark for the production pipeline.

Issues fixed during remote testing:

- systemd service execution did not resolve `python` when `PATH` was empty or
  too narrow. `CommandAdapter` now adds the current venv bin directory to
  `PATH` and rewrites `python`/`python3` to `sys.executable`.
- LeRobot 0.4.4 does not install a `lerobot-rollout` executable. Generated
  LeRobot deployment scripts now call the current `lerobot-record` policy
  rollout path instead.

Production 500-episode closed-loop run:

- run id:
  `20260608T165424Z-production-maniskill-lerobot-tabletop-pickcube-beed24c2`
- state dir: `/var/lib/open-embodied-simops/production-real-run-500`
- run dir:
  `/var/lib/open-embodied-simops/production-real-run-500/runs/20260608T165424Z-production-maniskill-lerobot-tabletop-pickcube-beed24c2`
- source simulator/data: ManiSkill 3.0.1 `PickCube-v1` motion planning, 500
  real generated successful demonstrations converted with LeRobot 0.4.4.
- final policy:
  `training/final_policy_act_default_lexfix_10000`
- deployment export:
  `deployment_act_default_lexfix_10000`

Additional real issues fixed in the production run:

- ManiSkill HDF5 trajectory groups are consumed by the LeRobot converter in
  lexicographic h5py order (`traj_0`, `traj_1`, `traj_10`, ...), not numeric
  order. The appended `observation.environment_state` data was regenerated in
  the same order as LeRobot rows to remove state/action misalignment.
- Policy evaluation now restores real HDF5 initial simulator state with
  `env.unwrapped.set_state_dict(...)`, applies LeRobot pre/post processors, and
  seeds Python/NumPy/PyTorch/CUDA per episode for reproducible stochastic
  policies.
- Deployment export configs now use `$SIMOPS_ROBOT_PORT` instead of
  `${SIMOPS_ROBOT_PORT}` so the SimOps template engine does not consume the
  runtime robot-port environment variable before generating `rollout.py`.

Model results from real ManiSkill rollouts:

- Diffusion on the corrected dataset did not pass: 20-episode seeded checkpoint
  comparison produced 9/20 at 5K, 11/20 at 10K, 11/20 at 15K, and 10/20 at 20K.
- ACT with the earlier small diagnostic chunk config did not pass.
- ACT with default LeRobot ACT chunking passed after 10K training steps:
  18/20 success on final-policy verification and 43/50 success on the stronger
  HDF5-state evaluation, with threshold 0.70.

Final accepted evaluation artifacts:

- 20-episode final policy metrics:
  `evaluation/act_default_lexfix_10000/final_policy_hdf5_state_metrics_20_seeded.json`
- 50-episode checkpoint metrics:
  `evaluation/act_default_lexfix_20000/checkpoint_010000_hdf5_state_metrics_50_seeded.json`
- final policy manifest:
  `training/final_policy_act_default_lexfix_10000_manifest.json`
- deployment manifest:
  `deployment_act_default_lexfix_10000/deployment_manifest.json`

Final provenance additions were appended to
`provenance/artifacts.jsonl` for:

- corrected LeRobot dataset: `lerobot_act_dataset_lexfix`
- ACT 10K checkpoint: `act_default_lexfix_10000_checkpoint`
- final ACT policy and manifest
- 50-episode evaluation report
- deployment manifest, ROS 2 rollout node, and LeRobot rollout launcher
