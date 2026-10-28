# Third-Party Components

This inventory is not a license grant for third-party software, assets, datasets,
model weights, voices or rendered media. Review the exact revision you distribute.
Installing a dependency does not grant permission to redistribute it.

| Component | Relationship | License handling |
| --- | --- | --- |
| Three.js | Vendored browser modules | Retain [upstream MIT notice](src/embodied_simops/web/vendor/THREE_LICENSE). |
| ManiSkill | Optional external simulation runtime | [Upstream license](https://github.com/mani-skill/ManiSkill/blob/main/LICENSE); check installed revision and asset licenses separately. |
| LeRobot | Optional external training/data runtime | [Upstream license](https://github.com/huggingface/lerobot/blob/main/LICENSE); model weights and datasets may have separate terms. |
| MotrixSim | Optional external runtime; not bundled | **Unverified installed-version and asset license.** Docs license must not be applied to the engine. See [vendor edition terms](https://motphys.com/en/motrixsim). |
| Infinigen / ProcTHOR / EmbodiedGen / RoboCasa / MimicGen / Genesis | Configured or planned external integrations | Do not imply complete integration or redistribution rights from a catalog entry. Verify each selected release and asset. |
| ROS 2 / MuJoCo / Gazebo / robomimic | External ecosystem / interfaces | Review the exact packages and assets before distribution; not bundled by this project. |

As checked on 2026-10-29, the MotrixSim product page distinguishes a noncommercial
community edition from commercial redistribution and embedding rights. The
version installed on the historical test host has not been re-inspected. The
adapter now records `NOASSERTION` rather than inventing a permissive license.

本仓库的许可证不会覆盖第三方仿真器、资产、数据集和模型权重。MotrixSim 暂作为
可选集成保留，不随开源代码分发其安装包或素材。公开前需核对实际版本的条款。
