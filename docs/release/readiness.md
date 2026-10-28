# Alpha Release Readiness / 开源发布检查

Audit date: 2026-10-29. This is a release-preparation record, not a production
acceptance certificate. Stars and adoption cannot be guaranteed.

## Positioning

**Open Embodied SimOps: a self-hosted workbench connecting robotics simulation,
datasets, training and evaluation, with traceable artifacts.**

定位：面向个人研究者和小型机器人团队的自托管具身智能实验工作台。
首要价值是可复现工作流与产物追踪，不是再次实现物理引擎，也不是“全能机器人操作系统”。

## Verified During This Audit

- Existing GitHub origin is a private, empty repository; local source has no
  initial commit yet. Public release and a license grant are pending confirmation.
- The original local test suite passed 33 tests. These include test doubles and
  are not GPU or real-robot acceptance evidence.
- A local directory secret scan reported no findings. This is not a guarantee
  that all files are legally publishable or free of sensitive information.
- The historical remote host timed out over SSH. No fresh remote/GPU validation
  or deployment was completed during this audit.
- MotrixSim license metadata incorrectly inherited Apache-2.0 from assumptions
  about upstream documentation. It is being changed to `NOASSERTION` pending
  exact runtime/asset review.

## Source Release Checks

- [x] Owner confirmed publication rights, existing repository and Apache-2.0 on 2026-10-29.
- [x] Original-code LICENSE and distribution metadata agree; third-party notices retained.
- [x] Staged-source Gitleaks scan found no leaks; private host address removed. No private assets included.
- [x] Local clean Python 3.11 environment: 35 core tests passed; build succeeded.
- [x] Upgrade local pip/setuptools; dependency audit reported no known vulnerabilities (project itself is not on PyPI and was skipped).
- [x] Repository is public, Apache-2.0 detected, private vulnerability reporting enabled.
- [x] Hosted Python 3.10/3.11 tests, builds and audits passed on commit `fbdab43` (run `40764189932`).
- [x] Hardware deployment is explicitly unverified in README and release notes.
- [ ] Confirm social accounts and rights to every video/audio asset before publishing.
- [ ] Verify each public post from its permalink; distinguish drafts, moderation and published playback.

## Full-Platform Acceptance (Not Claimed By This Alpha)

- [ ] Publish a reproducible supported-path installation and a new GPU acceptance record.
- [ ] Record an actual successful simulation/data/training/evaluation sequence with hashes.
- [ ] Validate real hardware separately, with calibration, limits and emergency stop.

## Product Gaps To Disclose

1. The native MotrixSim viewer and interactive bridge create separate simulation
   state. Embedding a window does not make the control/recording paths unified.
2. GPU serialization covers pipeline runs within one state directory, not all
   viewers, installs and interactive sessions on the host.
3. Generation includes built-in manifests and example-scene packaging; external
   text-to-3D/room generators still require configured tools and dependencies.
4. Session lifecycle, playback and concurrent renderer/worker access need stronger
   acceptance coverage. A returned session descriptor is not proof of replay.
5. The API is a trusted-local command runner without built-in authentication.
6. Exported ROS 2 / LeRobot interfaces do not demonstrate safe physical deployment.

## Historical Evaluation Boundary

The June 2026 notes report ACT results of 43/50 on demonstration-restored initial
states. This is historical, protocol-specific evidence, not a new benchmark,
unseen-task generalization result, or hardware success rate. Raw artifacts must
be recovered and revalidated before using any number in promotional material.

## Launch Narrative

Show one auditable task from configuration to policy evaluation. Lead with real
screens, then explain the provenance trail and single-user deployment model.
Publish the exact protocol, limitations and reproduction steps alongside it.
Do not buy stars, imply upstream endorsement, fabricate testimonials, or claim
all catalog integrations are complete.
