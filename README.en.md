# Open Embodied SimOps

**A self-hosted workbench connecting robotics simulation, datasets, training and
evaluation through traceable local workflows.**

[中文](README.md) · English · [Architecture](docs/architecture.md) · [Security](SECURITY.md) · [Contributing](CONTRIBUTING.md)

**Alpha, Apache-2.0.** Built for individual researchers and small robotics teams.
This is orchestration around existing engines, not a new physics engine or a
finished robot operations platform. Run it only in a trusted local environment.

```text
Scene + assets + robot + task + sensors + randomization
                          |
               Simulation and collection
                          |
           Dataset inspection / merge / conversion
                          |
                Policy training and evaluation
                          |
              ROS 2 / LeRobot interface export

     Declared artifacts -> source / version / license / SHA-256
```

## What Exists

- A Chinese-default bilingual web workbench with generation, assets, simulation,
  datasets, training and deployment pages.
- YAML task validation, command execution, logs, failure states and artifact
  tracking in SQLite/JSONL. Pipeline runs serialize within one state directory.
- ManiSkill PickCube/Panda collection and LeRobot integration code; ACT has a
  historical test record. Other policies and combinations need separate validation.
- Dataset inspection, merge and conversion tools; ROS 2 and LeRobot interface export.
- MotrixSim bridge and native-viewer integration code, subject to vendor licensing.

## What Is Not Proven

Built-in generation produces manifests or packages example scenes; it is not
general AI scene generation. External generators require installed dependencies
and configured commands. Catalog entries are not proof of complete integration.

The native MotrixSim viewer and bridge do not share one simulation state yet.
Interactive sessions and viewers are outside the pipeline's GPU lock. Exported
rollout interfaces have not been accepted on physical hardware. Recorded license
metadata is a declaration, not an independent legal or provenance certification.

See [release readiness](docs/release/readiness.md) for the current gaps.

## Run The Local Workbench

```sh
git clone https://github.com/eust-w/open-embodied-simops.git
cd open-embodied-simops
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest
python -m uvicorn embodied_simops.api:app --host 127.0.0.1 --port 18080
```

Open <http://127.0.0.1:18080>. This starts the control plane, not a verified GPU
runtime. Core tests include doubles and are not simulator or robot acceptance.
The API runs configured commands and has no built-in authentication. Never expose
it, the simulation bridge, or noVNC directly to the Internet.

For the robotics path, inspect the environment variables and commands in the
[ManiSkill/LeRobot example](examples/mvp_maniskill_lerobot_tabletop.yaml), prepare
separate compatible environments, then run:

```sh
simops validate examples/mvp_maniskill_lerobot_tabletop.yaml
simops run examples/mvp_maniskill_lerobot_tabletop.yaml --state-dir .simops
```

Heavy runtimes, model weights and assets are not bundled. Installation helpers
still depend on compatible drivers, network access and upstream licenses. A
fully locked, clean-machine GPU installation remains release work.

## Hardware And Evidence

The design targets a single RTX 5880 48GB, with 128GB RAM and 2–4TB NVMe recommended.
This is not a measured capacity guarantee. Do not overlap training, 3D generation
and large simulation jobs.

The [June 2026 record](docs/remote-real-test-2026-06-08.md) describes a ManiSkill →
LeRobot ACT → simulation evaluation → interface-export experiment. Evaluation
used demonstration-restored initial states, not unseen tasks or real hardware.
The historical GPU host could not be reached during the 2026-10-29 release audit;
there is no fresh remote acceptance claim.

## License And Contributions

Original code is [Apache-2.0](LICENSE). Dependencies, assets and weights retain
their own terms; see [third-party notices](THIRD_PARTY_NOTICES.md). MotrixSim is
optional and its installed-version license remains unverified, not Apache-2.0
content supplied by this project.

Help improve reproducible installation, shared session state, GPU scheduling,
and real integration acceptance. See [contribution guidance](CONTRIBUTING.md).
