import pytest
from fastapi import HTTPException

from embodied_simops.api import (
    ConfigBuildRequest,
    DatasetMergeRequest,
    GenerationRequest,
    SimulationSessionRequest,
    TeleopSessionRequest,
    create_config,
    create_generation_job,
    create_simulation_session,
    create_simulation_preview,
    create_teleop_session,
    get_simulation_native_ui,
    get_asset_library,
    get_asset_preview,
    get_catalog,
    get_runtime_status,
    inspect_dataset,
    list_datasets,
    list_deployments,
    list_generation_jobs,
    list_models,
    merge_datasets,
    _frame_image_bytes,
)
from embodied_simops.config import load_task_config
from embodied_simops.provenance import sha256_path


def _write_test_motrixsim_install(tmp_path):
    pythonpath = tmp_path / "site"
    package = pythonpath / "motrixsim"
    package.mkdir(parents=True)
    package.joinpath("__init__.py").write_text(
        """
from pathlib import Path

__version__ = "0.0.test"


class SceneModel:
    def __init__(self, path):
        self.path = str(path)
        self.geom_names = ["floor", "cube"]
        self.num_geoms = 2


class SceneData:
    def __init__(self, model):
        self.model = model
        self.dof_pos = [0.0]
        self.dof_vel = [0.0]
        self.actuator_ctrls = []


def load_model(path):
    xml_path = Path(path)
    if not xml_path.exists():
        raise FileNotFoundError(path)
    return SceneModel(xml_path)


def step(model, data):
    data.dof_pos = [data.dof_pos[0] + 1.0]
    data.dof_vel = [1.0]
""",
        encoding="utf-8",
    )

    docs = tmp_path / "motrixsim-docs"
    body_xml = docs / "examples" / "assets" / "body.xml"
    panda_xml = docs / "examples" / "assets" / "franka_emika_panda" / "scene.xml"
    body_xml.parent.mkdir(parents=True)
    panda_xml.parent.mkdir(parents=True)
    body_xml.write_text(
        """
<mujoco>
  <worldbody>
    <geom name="floor" type="plane" size="5 5 0.1" pos="0 0 0" rgba="0.8 0.9 0.8 1"/>
    <body name="free_cube" pos="0 0 1.5">
      <geom name="cube" type="box" size="0.25 0.25 0.25" pos="0 0 0" rgba="1 0 0 1"/>
    </body>
    <body name="sphere" pos="2 0 1.5">
      <geom name="sphere" type="sphere" size="0.25" pos="0 0 0" rgba="0 1 0 1"/>
    </body>
  </worldbody>
</mujoco>
""",
        encoding="utf-8",
    )
    panda_xml.write_text("<mujoco model='panda scene'><worldbody><geom name='floor' type='plane'/></worldbody></mujoco>", encoding="utf-8")
    home = tmp_path / "MotrixLab"
    home.mkdir()
    return {"pythonpath": pythonpath, "docs": docs, "home": home}


def _configure_test_motrixsim(monkeypatch, install, python):
    monkeypatch.setenv("SIMOPS_MOTRIXSIM_PYTHON", python)
    monkeypatch.setenv("SIMOPS_MOTRIXSIM_PYTHONPATH", str(install["pythonpath"]))
    monkeypatch.setenv("SIMOPS_MOTRIXSIM_DOCS", str(install["docs"]))
    monkeypatch.setenv("SIMOPS_MOTRIXSIM_HOME", str(install["home"]))


def test_catalog_exposes_available_and_unconfigured_capabilities(monkeypatch):
    monkeypatch.delenv("SIMOPS_TELEOP_BRIDGE_URL", raising=False)
    monkeypatch.delenv("SIMOPS_LEROBOT_PYTHON", raising=False)
    monkeypatch.setenv("SIMOPS_DEFAULT_TELEOP_BRIDGE_URL", "http://127.0.0.1:9")

    catalog = get_catalog()

    assert any(item["id"] == "maniskill" and item["status"] == "available" for item in catalog["simulators"])
    assert any(item["id"] == "infinigen" and item["status"] == "unconfigured" for item in catalog["scene_generators"])
    assert any(item["id"] == "PickCube-v1" and item["label_zh"] == "拿起方块到目标" for item in catalog["tasks"])
    assert catalog["default_state_dir"] == ".simops"
    assert catalog["teleop"]["status"] == "not_configured"
    assert catalog["simulation_api"]["status"] == "not_configured"
    assert "managed simops-bridge.service" in catalog["simulation_api"]["required_env"][0]
    assert any(
        item["id"] == "merge_lerobot" and item["status"] == "requires_SIMOPS_LEROBOT_PYTHON"
        for item in catalog["dataset_operations"]
    )
    assert "POST /simulations/sessions" in catalog["simulation_api"]["public_endpoints"]


def test_catalog_exposes_real_motrixsim_when_installed(monkeypatch, tmp_path):
    install = _write_test_motrixsim_install(tmp_path)
    _configure_test_motrixsim(monkeypatch, install, python=__import__("sys").executable)

    catalog = get_catalog()

    motrixsim = next(item for item in catalog["simulators"] if item["id"] == "motrixsim")
    generator = next(item for item in catalog["scene_generators"] if item["id"] == "motrixsim_examples")
    runtime_component = next(item for item in catalog["runtime_dependencies"]["components"] if item["id"] == "motrixsim")

    assert motrixsim["status"] == "available"
    assert motrixsim["version"] == "0.0.test"
    assert motrixsim["license"] == "NOASSERTION"
    assert generator["status"] == "available"
    assert generator["simulator"] == "motrixsim"
    assert any(item["id"] == "motrix_panda" and item["status"] == "available" for item in catalog["robots"])
    assert any(item["id"] == "MotrixSimStep" and item["status"] == "available" for item in catalog["tasks"])
    assert runtime_component["status"] == "available"
    assert runtime_component["step_ok"] is True


def test_create_config_writes_valid_real_maniskill_task(tmp_path):
    response = create_config(
        ConfigBuildRequest(
            state_dir=str(tmp_path / "state"),
            name="ui-test-pickcube",
            demo_episodes=3,
            train_steps=10,
            eval_episodes=2,
            dataset_repo_id="simops/ui-test-pickcube",
        )
    )

    config_path = response["config_path"]
    task = load_task_config(config_path)

    assert response["status"] == "valid"
    assert task.name == "ui-test-pickcube"
    assert task.pipeline[0].adapter == "dependency_check"
    assert task.pipeline[-1].adapter == "deployment_export"
    assert "$SIMOPS_ROBOT_PORT" in response["config_yaml"]
    assert "${SIMOPS_ROBOT_PORT}" not in response["config_yaml"]
    train_stage = next(stage for stage in task.pipeline if stage.id == "train_policy")
    assert (
        "--policy.normalization_mapping={VISUAL: MEAN_STD, STATE: MEAN_STD, ACTION: MEAN_STD, ENV: MEAN_STD}"
        in train_stage.command
    )


def test_create_collect_config_only_runs_dependency_and_collection(tmp_path):
    response = create_config(
        ConfigBuildRequest(
            state_dir=str(tmp_path / "state"),
            name="ui-test-pickcube-collect",
            demo_episodes=1,
            pipeline_mode="collect",
        )
    )

    task = load_task_config(response["config_path"])

    assert [stage.id for stage in task.pipeline] == [
        "check_runtime",
        "collect_motionplanned_tabletop_data",
    ]
    assert task.stack["training_strategy"]["steps"] == 0


def test_runtime_status_reports_required_env(monkeypatch):
    monkeypatch.setenv("SIMOPS_MANISKILL_MP_PYTHON", "/bin/sh")
    monkeypatch.setenv("SIMOPS_LEROBOT_PYTHON", "/bin/sh")
    monkeypatch.setenv("SIMOPS_LEROBOT_TRAIN", "/bin/sh")
    monkeypatch.setenv("SIMOPS_LEROBOT_RECORD", "/bin/sh")

    status = get_runtime_status()

    assert status["can_run_pipeline"] is True
    assert {item["env"] for item in status["checks"]} == {
        "SIMOPS_MANISKILL_MP_PYTHON",
        "SIMOPS_LEROBOT_PYTHON",
        "SIMOPS_LEROBOT_TRAIN",
        "SIMOPS_LEROBOT_RECORD",
    }


def test_maniskill_generation_materializes_scene_asset_package(tmp_path):
    response = create_generation_job(
        GenerationRequest(
            state_dir=str(tmp_path / "state"),
            name="ui-generated-tabletop",
            generator="maniskill_tabletop",
            kind="package",
            assets=["cube", "tabletop", "goal"],
            count=1,
            seed=7,
        )
    )

    jobs = list_generation_jobs(state_dir=str(tmp_path / "state"))

    assert response["status"] == "succeeded"
    assert response["sha256"]
    assert response["size_bytes"] > 0
    assert response["source_components"][0]["source"]["license"] == "Apache-2.0"
    assert {artifact["role"] for artifact in response["artifacts"]} == {
        "scene_manifest",
        "asset_manifest",
        "preview_scene",
    }
    assert jobs[0]["id"] == response["id"]
    package_sha, package_size = sha256_path(tmp_path / "state" / "generation" / response["id"])
    assert response["sha256"] == package_sha
    assert response["size_bytes"] == package_size
    assert jobs[0]["sha256"] == package_sha
    assert jobs[0]["size_bytes"] == package_size
    assert any(item["role"] == "preview_scene" for item in response["artifacts"])


def test_motrixsim_generation_imports_installed_example_package(monkeypatch, tmp_path):
    install = _write_test_motrixsim_install(tmp_path)
    _configure_test_motrixsim(monkeypatch, install, python=__import__("sys").executable)

    response = create_generation_job(
        GenerationRequest(
            state_dir=str(tmp_path / "state"),
            name="motrixsim-body-package",
            generator="motrixsim_examples",
            kind="package",
            scene="motrixsim_body",
            assets=["body", "cube", "sphere"],
            task="MotrixSimStep",
            count=1,
            seed=17,
        )
    )
    preview = get_asset_preview(manifest_path=response["path"])

    assert response["status"] == "succeeded"
    assert response["simulator"] == "motrixsim"
    assert response["source_components"][0]["source"]["license"] == "NOASSERTION"
    assert response["source_components"][0]["source"]["version"] == "0.0.test"
    assert {artifact["role"] for artifact in response["artifacts"]} >= {
        "motrix_scene_xml",
        "motrix_validation",
        "preview_scene",
    }
    assert preview["source"]["license"] == "NOASSERTION"
    assert preview["package_manifest"]["sha256"]
    assert {item["id"] for item in preview["objects"]} >= {"floor", "cube", "sphere"}


def test_asset_preview_reads_generation_manifest(tmp_path):
    response = create_generation_job(
        GenerationRequest(
            state_dir=str(tmp_path / "state"),
            name="preview-tabletop",
            generator="maniskill_tabletop",
            kind="package",
            assets=["cube", "tabletop", "goal"],
            seed=22,
        )
    )

    preview = get_asset_preview(manifest_path=response["path"])

    assert preview["schema_version"] == "simops.preview_scene/v1"
    assert preview["source"]["license"] == "Apache-2.0"
    assert preview["package_manifest"]["sha256"]
    assert {item["id"] for item in preview["objects"]} >= {"tabletop", "cube", "goal"}


def test_simulation_preview_uses_real_task_configuration():
    preview = create_simulation_preview(
        SimulationSessionRequest(
            simulator="maniskill",
            robot="panda",
            scene="maniskill_tabletop",
            task="PickCube-v1",
            assets=["cube", "tabletop", "goal"],
            randomization_seed=33,
        )
    )

    assert preview["task"] == "PickCube-v1"
    assert preview["renderer"] == "three.js"
    assert any(item["id"] == "panda_base" for item in preview["objects"])


def test_simulation_preview_supports_motrixsim_package(monkeypatch, tmp_path):
    install = _write_test_motrixsim_install(tmp_path)
    _configure_test_motrixsim(monkeypatch, install, python=__import__("sys").executable)

    preview = create_simulation_preview(
        SimulationSessionRequest(
            simulator="motrixsim",
            robot="motrix_body",
            scene="motrixsim_body",
            task="MotrixSimStep",
            assets=["body", "cube", "sphere"],
            randomization_seed=4,
        )
    )

    assert preview["scene"] == "motrixsim_body"
    assert preview["source"]["license"] == "NOASSERTION"
    assert any(item["id"] == "cube" for item in preview["objects"])


def test_simulation_frame_stream_uses_real_image_payload():
    assert _frame_image_bytes(
        {
            "media_type": "image/png",
            "encoding": "base64",
            "data_base64": "iVBORw0KGgo=",
        }
    ) == b"\x89PNG\r\n\x1a\n"
    assert _frame_image_bytes({"media_type": "application/json", "encoding": "json"}) is None


def test_native_simulator_ui_reports_headless_stream_without_embedded_url(monkeypatch):
    monkeypatch.delenv("SIMOPS_NATIVE_SIM_UI_URL", raising=False)
    monkeypatch.delenv("SIMOPS_NOVNC_URL", raising=False)

    payload = get_simulation_native_ui()

    assert payload["status"] == "not_configured"
    assert payload["mode"] == "headless_render_stream"
    assert "SIMOPS_NATIVE_SIM_UI_URL" in payload["required_env"]


def test_product_asset_library_reads_generated_manifests(tmp_path):
    create_generation_job(
        GenerationRequest(
            state_dir=str(tmp_path / "state"),
            name="library-tabletop",
            generator="maniskill_tabletop",
            kind="package",
            assets=["cube", "tabletop", "goal"],
            count=1,
            seed=11,
        )
    )

    library = get_asset_library(state_dir=str(tmp_path / "state"))

    assert library["scenes"][0]["source"]["license"] == "Apache-2.0"
    assert library["assets"][0]["assets"] == ["cube", "tabletop", "goal"]
    assert library["generated_packages"][0]["sha256"]


def test_dataset_resource_discovers_real_lerobot_layout(tmp_path):
    dataset_root = tmp_path / "state" / "datasets" / "lerobot_pickcube"
    (dataset_root / "meta").mkdir(parents=True)
    (dataset_root / "data" / "chunk-000").mkdir(parents=True)
    (dataset_root / "meta" / "info.json").write_text(
        '{"fps":30,"total_frames":2,"total_episodes":1,"features":{"action":{"dtype":"float32","shape":[7]}}}',
        encoding="utf-8",
    )
    (dataset_root / "meta" / "stats.json").write_text('{"action":{"mean":[0]}}', encoding="utf-8")
    (dataset_root / "data" / "chunk-000" / "file-000.parquet").write_bytes(b"PAR1")

    datasets = list_datasets(state_dir=str(tmp_path / "state"))
    detail = inspect_dataset(path=str(dataset_root))

    assert datasets[0]["total_frames"] == 2
    assert datasets[0]["feature_count"] == 1
    assert detail["info"]["fps"] == 30
    assert detail["files"]


def test_model_and_deployment_resources_are_empty_without_artifacts(tmp_path):
    assert list_models(state_dir=str(tmp_path / "state")) == []
    assert list_deployments(state_dir=str(tmp_path / "state")) == []


def test_external_generation_requires_real_command(monkeypatch, tmp_path):
    monkeypatch.delenv("SIMOPS_INFINIGEN_COMMAND", raising=False)

    with pytest.raises(HTTPException) as excinfo:
        create_generation_job(
            GenerationRequest(
                state_dir=str(tmp_path / "state"),
                name="infinigen-scene",
                generator="infinigen",
            )
        )

    assert excinfo.value.status_code == 503
    assert "refusing to fake" in excinfo.value.detail


def test_create_config_rejects_unwired_robot(tmp_path):
    with pytest.raises(HTTPException) as excinfo:
        create_config(
            ConfigBuildRequest(
                state_dir=str(tmp_path / "state"),
                robot="so100_follower",
            )
        )

    assert excinfo.value.status_code == 400
    assert "not wired to a real local pipeline" in excinfo.value.detail


def test_teleop_requires_real_bridge(monkeypatch):
    monkeypatch.delenv("SIMOPS_TELEOP_BRIDGE_URL", raising=False)
    monkeypatch.setenv("SIMOPS_DEFAULT_TELEOP_BRIDGE_URL", "http://127.0.0.1:9")

    with pytest.raises(HTTPException) as excinfo:
        create_teleop_session(
            TeleopSessionRequest(
                simulator="maniskill",
                robot="panda",
                scene="maniskill_tabletop",
                task="PickCube-v1",
            )
        )

    assert excinfo.value.status_code == 503
    assert "managed simulation bridge is not reachable" in excinfo.value.detail


def test_simulation_session_requires_real_bridge(monkeypatch):
    monkeypatch.delenv("SIMOPS_TELEOP_BRIDGE_URL", raising=False)
    monkeypatch.setenv("SIMOPS_DEFAULT_TELEOP_BRIDGE_URL", "http://127.0.0.1:9")

    with pytest.raises(HTTPException) as excinfo:
        create_simulation_session(
            SimulationSessionRequest(
                simulator="maniskill",
                robot="panda",
                scene="maniskill_tabletop",
                task="PickCube-v1",
                assets=["cube", "tabletop", "goal"],
            )
        )

    assert excinfo.value.status_code == 503
    assert "managed simulation bridge is not reachable" in excinfo.value.detail


def test_motrixsim_session_uses_real_bridge_instead_of_api_side_fake(monkeypatch, tmp_path):
    install = _write_test_motrixsim_install(tmp_path)
    _configure_test_motrixsim(monkeypatch, install, python=__import__("sys").executable)
    monkeypatch.delenv("SIMOPS_TELEOP_BRIDGE_URL", raising=False)
    monkeypatch.setenv("SIMOPS_DEFAULT_TELEOP_BRIDGE_URL", "http://127.0.0.1:9")

    with pytest.raises(HTTPException) as excinfo:
        create_simulation_session(
            SimulationSessionRequest(
                simulator="motrixsim",
                robot="motrix_body",
                scene="motrixsim_body",
                task="MotrixSimStep",
                assets=["body"],
            )
        )

    assert excinfo.value.status_code == 503
    assert "managed simulation bridge is not reachable" in excinfo.value.detail


def test_dataset_merge_requires_lerobot_python(monkeypatch):
    monkeypatch.delenv("SIMOPS_LEROBOT_PYTHON", raising=False)

    with pytest.raises(HTTPException) as excinfo:
        merge_datasets(
            DatasetMergeRequest(
                dataset_paths=["/data/a", "/data/b"],
                output_path="/data/merged",
            )
        )

    assert excinfo.value.status_code == 503
    assert "SIMOPS_LEROBOT_PYTHON" in excinfo.value.detail
