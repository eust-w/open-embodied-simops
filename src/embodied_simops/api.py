from __future__ import annotations

import base64
import json
import os
import random
import re
import shutil
import shlex
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from embodied_simops import __version__
from embodied_simops.config import ConfigError, load_task_config
from embodied_simops.integrations.motrixsim import (
    MOTRIXSIM_EXAMPLE_SCENES,
    MOTRIXSIM_LICENSE,
    build_motrixsim_preview_scene,
    materialize_motrixsim_generation,
    motrixsim_probe,
    motrixsim_runtime_component,
    motrixsim_scene_xml,
)
from embodied_simops.orchestrator import PipelineError, SimOpsEngine
from embodied_simops.provenance import sha256_path
from embodied_simops.storage import SimOpsStore


WEB_DIR = Path(__file__).with_name("web")


class RunRequest(BaseModel):
    config_path: str
    state_dir: str = ".simops"
    env: dict[str, str] = Field(default_factory=dict)


class ConfigBuildRequest(BaseModel):
    state_dir: str = ".simops"
    name: str = "production-maniskill-lerobot-tabletop-pickcube"
    simulator: str = "maniskill"
    robot: str = "panda"
    scene: str = "maniskill_tabletop"
    assets: list[str] = Field(default_factory=lambda: ["cube", "tabletop", "goal"])
    task: str = "PickCube-v1"
    sensor_preset: str = "state_dict_rgb"
    randomization_seed: int = 20260608
    randomization_domains: list[str] = Field(default_factory=lambda: ["object_pose", "camera_pose"])
    demo_episodes: int = Field(default=50, ge=1)
    data_format: str = "lerobot"
    policy_type: str = "act"
    train_steps: int = Field(default=10000, ge=1)
    batch_size: int = Field(default=64, ge=1)
    eval_episodes: int = Field(default=20, ge=1)
    eval_max_steps: int = Field(default=120, ge=1)
    min_success_rate: float = Field(default=0.7, ge=0.0, le=1.0)
    dataset_repo_id: str = "simops/pickcube-real-ui"
    deployment_targets: list[str] = Field(default_factory=lambda: ["ros2", "lerobot_rollout"])
    pipeline_mode: str = "full"


class TeleopSessionRequest(BaseModel):
    simulator: str
    robot: str
    scene: str
    task: str
    assets: list[str] = Field(default_factory=list)


class TeleopActionRequest(BaseModel):
    action: str
    velocity: float = Field(default=0.25, ge=0.0, le=1.0)


class SimulationSessionRequest(BaseModel):
    state_dir: str = ".simops"
    config_path: str | None = None
    simulator: str
    robot: str
    scene: str
    task: str
    assets: list[str] = Field(default_factory=list)
    sensor_preset: str = "state_dict_rgb"
    randomization_seed: int = 20260608
    mode: str = "interactive"
    render_width: int = Field(default=1280, ge=64, le=4096)
    render_height: int = Field(default=720, ge=64, le=4096)


class SimulationActionRequest(BaseModel):
    action: str
    velocity: float = Field(default=0.25, ge=0.0, le=1.0)


class SimulationPlaybackRequest(BaseModel):
    source_run_id: str | None = None
    artifact_path: str | None = None
    speed: float = Field(default=1.0, gt=0.0, le=10.0)
    loop: bool = False


class DatasetMergeRequest(BaseModel):
    dataset_paths: list[str] = Field(min_length=2)
    output_path: str


class RuntimeInstallRequest(BaseModel):
    components: list[str] = Field(min_length=1)
    project_dir: str = "/opt/open-embodied-simops"


class GenerationRequest(BaseModel):
    state_dir: str = ".simops"
    name: str = "generated-tabletop-package"
    generator: str = "maniskill_tabletop"
    kind: str = "package"
    scene: str = "maniskill_tabletop"
    assets: list[str] = Field(default_factory=lambda: ["cube", "tabletop", "goal"])
    task: str = "PickCube-v1"
    count: int = Field(default=1, ge=1, le=100)
    seed: int = 20260609
    output_format: str = "simops_manifest"


app = FastAPI(title="Open Embodied SimOps", version=__version__)

if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    index_path = WEB_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="frontend assets are not installed")
    return FileResponse(index_path, headers={"Cache-Control": "no-store"})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/catalog")
def get_catalog() -> dict[str, Any]:
    return _catalog()


@app.get("/runtime/status")
def get_runtime_status() -> dict[str, Any]:
    checks = []
    for env_name in _runtime_env_requirements():
        value = os.environ.get(env_name, "")
        resolved = shutil.which(value) if value else None
        path = Path(value) if value else None
        checks.append(
            {
                "env": env_name,
                "value": value,
                "configured": bool(value),
                "executable": bool(resolved or (path and path.exists() and os.access(path, os.X_OK))),
            }
        )
    return {
        "state_dir": _default_state_dir(),
        "checks": checks,
        "can_run_pipeline": all(item["configured"] and item["executable"] for item in checks),
    }


@app.get("/runtime/dependencies")
def get_runtime_dependencies() -> dict[str, Any]:
    return _runtime_dependencies()


@app.post("/runtime/dependencies/install")
def install_runtime_dependencies(request: RuntimeInstallRequest) -> dict[str, Any]:
    allowed = {"maniskill", "lerobot", "bridge_service", "native_ui"}
    unknown = sorted(set(request.components) - allowed)
    if unknown:
        raise HTTPException(status_code=400, detail=f"unsupported runtime components: {', '.join(unknown)}")

    results = []
    for component in request.components:
        if component == "bridge_service":
            command = [
                sys.executable,
                "-m",
                "embodied_simops.bootstrap",
                "install-bridge-service",
                "--project-dir",
                request.project_dir,
            ]
        elif component == "native_ui":
            command = [
                sys.executable,
                "-m",
                "embodied_simops.bootstrap",
                "install-native-ui-service",
                "--project-dir",
                request.project_dir,
            ]
        else:
            command = [
                sys.executable,
                "-m",
                "embodied_simops.bootstrap",
                "install-component",
                component,
                "--project-dir",
                request.project_dir,
            ]
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
        results.append(
            {
                "component": component,
                "command": command,
                "returncode": completed.returncode,
                "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-4000:],
                "status": "succeeded" if completed.returncode == 0 else "failed",
            }
        )
        if completed.returncode != 0:
            raise HTTPException(status_code=500, detail=results)
    return {"status": "succeeded", "results": results, "dependencies": _runtime_dependencies()}


@app.post("/configs")
def create_config(request: ConfigBuildRequest) -> dict[str, Any]:
    config = _build_real_maniskill_config(request)
    state_dir = Path(request.state_dir)
    config_dir = state_dir / "configs"
    config_dir.mkdir(parents=True, exist_ok=True)

    config_path = _unique_config_path(config_dir, request.name)
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    try:
        task = load_task_config(config_path)
    except ConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "status": "valid",
        "name": task.name,
        "config_path": str(config_path),
        "config_yaml": config_path.read_text(encoding="utf-8"),
        "required_env": _runtime_env_requirements(),
    }


@app.post("/generation/jobs")
def create_generation_job(request: GenerationRequest) -> dict[str, Any]:
    if request.generator == "maniskill_tabletop":
        return _materialize_maniskill_generation(request)
    if request.generator == "motrixsim_examples":
        return _materialize_motrixsim_generation(request)
    return _run_external_generation(request)


@app.get("/generation/jobs")
def list_generation_jobs(state_dir: str = ".simops", limit: int = 50) -> list[dict[str, Any]]:
    generation_dir = Path(state_dir) / "generation"
    if not generation_dir.exists():
        return []

    jobs = []
    for manifest_path in sorted(generation_dir.glob("*/package_manifest.json"), reverse=True):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            digest, size_bytes = sha256_path(manifest_path.parent)
            manifest["path"] = str(manifest_path.parent)
            manifest["sha256"] = digest
            manifest["size_bytes"] = size_bytes
            jobs.append(manifest)
        except (OSError, json.JSONDecodeError):
            continue
        if len(jobs) >= limit:
            break
    return jobs


@app.post("/tasks/validate")
def validate_task(request: RunRequest) -> dict[str, str]:
    try:
        task = load_task_config(request.config_path)
    except ConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "valid", "name": task.name}


@app.post("/runs")
def create_run(request: RunRequest) -> dict[str, str]:
    config_path = Path(request.config_path)
    state_dir = Path(request.state_dir)

    try:
        task = load_task_config(config_path)
    except ConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        with _temporary_env(request.env):
            result = SimOpsEngine(state_dir).run(task)
    except PipelineError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": result.status, "name": task.name, "run_id": result.run_id, "run_dir": str(result.run_dir)}


@app.get("/runs")
def list_runs(state_dir: str = ".simops", limit: int = 50) -> list[dict]:
    return SimOpsStore(state_dir).list_runs(limit=limit)


@app.get("/runs/{run_id}")
def get_run(run_id: str, state_dir: str = ".simops") -> dict:
    record = SimOpsStore(state_dir).get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="run not found")
    return record


@app.get("/runs/{run_id}/stages")
def get_run_stages(run_id: str, state_dir: str = ".simops") -> list[dict]:
    return SimOpsStore(state_dir).get_stages(run_id)


@app.get("/runs/{run_id}/artifacts")
def get_run_artifacts(run_id: str, state_dir: str = ".simops") -> list[dict]:
    return SimOpsStore(state_dir).get_artifacts(run_id)


@app.get("/artifacts")
def list_artifacts(state_dir: str = ".simops", role: str | None = None, limit: int = 200) -> list[dict]:
    return SimOpsStore(state_dir).list_artifacts(role=role, limit=limit)


@app.get("/assets/library")
def get_asset_library(state_dir: str = ".simops") -> dict[str, Any]:
    generation_jobs = list_generation_jobs(state_dir=state_dir, limit=200)
    scenes = []
    assets = []
    for job in generation_jobs:
        scene_artifact = next((item for item in job.get("artifacts", []) if item.get("role") == "scene_manifest"), None)
        asset_artifact = next((item for item in job.get("artifacts", []) if item.get("role") == "asset_manifest"), None)
        if scene_artifact:
            scenes.append(
                {
                    "id": job["id"],
                    "name": job["name"],
                    "generator": job["generator"],
                    "path": scene_artifact["path"],
                    "sha256": scene_artifact["sha256"],
                    "source": scene_artifact.get("source") or _first_source(job),
                    "status": job.get("status", "succeeded"),
                }
            )
        if asset_artifact:
            assets.append(
                {
                    "id": job["id"],
                    "name": job["name"],
                    "assets": job.get("assets", []),
                    "path": asset_artifact["path"],
                    "sha256": asset_artifact["sha256"],
                    "source": asset_artifact.get("source") or _first_source(job),
                    "status": job.get("status", "succeeded"),
                }
            )
    return {
        "state_dir": state_dir,
        "generated_packages": generation_jobs,
        "scenes": scenes,
        "assets": assets,
        "robots": _catalog()["robots"],
    }


@app.get("/assets/preview")
def get_asset_preview(manifest_path: str) -> dict[str, Any]:
    path = Path(manifest_path)
    if path.is_dir():
        path = path / "package_manifest.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="package manifest not found")
    manifest = _read_json_if_exists(path)
    if manifest.get("schema_version") != "simops.generation/v1":
        raise HTTPException(status_code=400, detail="path is not a SimOps generation manifest")
    return _preview_scene_from_generation_manifest(manifest, path)


@app.post("/simulations/preview")
def create_simulation_preview(request: SimulationSessionRequest) -> dict[str, Any]:
    if request.simulator == "motrixsim":
        try:
            return build_motrixsim_preview_scene(
                name=f"{request.robot}-{request.task}",
                scene=request.scene,
                task=request.task,
                assets=request.assets,
                seed=request.randomization_seed,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    if request.simulator != "maniskill":
        raise HTTPException(status_code=400, detail=f"3D preview currently supports maniskill only, got {request.simulator}")
    if request.task != "PickCube-v1":
        raise HTTPException(status_code=400, detail=f"3D preview currently supports PickCube-v1 only, got {request.task}")
    return _build_maniskill_preview_scene(
        name=f"{request.robot}-{request.task}",
        scene=request.scene,
        task=request.task,
        assets=request.assets,
        seed=request.randomization_seed,
        source={
            "uri": "https://github.com/haosulab/ManiSkill",
            "version": "3.0.1",
            "license": "Apache-2.0",
        },
        include_robot=request.robot == "panda",
        generated_from=[],
    )


@app.get("/datasets")
def list_datasets(state_dir: str = ".simops", limit: int = 200) -> list[dict[str, Any]]:
    state = Path(state_dir)
    discovered: dict[str, dict[str, Any]] = {}
    try:
        artifacts = SimOpsStore(state).list_artifacts(role="lerobot_dataset", limit=limit)
    except sqlite3.Error:
        artifacts = []
    for artifact in artifacts:
        item = _dataset_summary(Path(artifact["path"]), artifact=artifact)
        discovered[item["path"]] = item

    if state.exists():
        for info_path in sorted(state.rglob("meta/info.json"), reverse=True):
            if len(discovered) >= limit:
                break
            root = info_path.parents[1]
            if (root / "data").exists():
                item = _dataset_summary(root, artifact=None)
                discovered.setdefault(item["path"], item)
    return list(discovered.values())[:limit]


@app.get("/datasets/inspect")
def inspect_dataset(path: str) -> dict[str, Any]:
    dataset_path = Path(path)
    if not dataset_path.exists():
        raise HTTPException(status_code=404, detail="dataset path not found")
    return _dataset_summary(dataset_path, artifact=None) | {
        "info": _read_json_if_exists(dataset_path / "meta" / "info.json"),
        "stats": _read_json_if_exists(dataset_path / "meta" / "stats.json"),
        "files": [str(item) for item in sorted(dataset_path.rglob("*")) if item.is_file()][:200],
    }


@app.get("/models")
def list_models(state_dir: str = ".simops", limit: int = 200) -> list[dict[str, Any]]:
    store = SimOpsStore(state_dir)
    artifacts = []
    for role in ("model", "model_manifest", "training_run"):
        artifacts.extend(store.list_artifacts(role=role, limit=limit))
    return [_artifact_product_summary(artifact) for artifact in artifacts[:limit]]


@app.get("/deployments")
def list_deployments(state_dir: str = ".simops", limit: int = 200) -> list[dict[str, Any]]:
    store = SimOpsStore(state_dir)
    artifacts = store.list_artifacts(role="deployment_interface", limit=limit)
    deployments = [_artifact_product_summary(artifact) for artifact in artifacts[:limit]]
    for run in store.list_runs(limit=limit):
        manifest_path = Path(run["run_dir"]) / "deployment" / "deployment_manifest.json"
        if manifest_path.exists():
            digest, size = sha256_path(manifest_path)
            deployments.append(
                {
                    "name": "deployment_manifest",
                    "role": "deployment_manifest",
                    "run_id": run["id"],
                    "path": str(manifest_path),
                    "sha256": digest,
                    "size_bytes": size,
                    "status": run["status"],
                }
            )
    return deployments[:limit]


@app.post("/datasets/merge")
def merge_datasets(request: DatasetMergeRequest) -> dict[str, Any]:
    lerobot_python = os.environ.get("SIMOPS_LEROBOT_PYTHON")
    if not lerobot_python:
        raise HTTPException(
            status_code=503,
            detail="SIMOPS_LEROBOT_PYTHON is not configured; cannot run built-in LeRobot merge",
        )
    command = [
        lerobot_python,
        "-m",
        "embodied_simops.dataset_ops",
        "merge-lerobot",
        "--output",
        request.output_path,
        *request.dataset_paths,
    ]

    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=completed.stderr.strip() or completed.stdout.strip(),
        )
    try:
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        payload = {"status": "succeeded", "output_path": request.output_path}
    return payload


@app.post("/teleop/sessions")
def create_teleop_session(request: TeleopSessionRequest) -> dict[str, Any]:
    return _bridge_post("/sessions", request.model_dump())


@app.post("/teleop/sessions/{session_id}/actions")
def send_teleop_action(session_id: str, request: TeleopActionRequest) -> dict[str, Any]:
    return _bridge_post(f"/sessions/{_bridge_segment(session_id)}/actions", request.model_dump())


@app.post("/simulations/sessions")
def create_simulation_session(request: SimulationSessionRequest) -> dict[str, Any]:
    return _bridge_post("/sessions", request.model_dump(exclude_none=True))


@app.get("/simulations/sessions")
def list_simulation_sessions() -> dict[str, Any]:
    return _bridge_get("/sessions")


@app.get("/simulations/sessions/{session_id}")
def get_simulation_session(session_id: str) -> dict[str, Any]:
    return _bridge_get(f"/sessions/{_bridge_segment(session_id)}")


@app.delete("/simulations/sessions/{session_id}")
def close_simulation_session(session_id: str) -> dict[str, Any]:
    return _bridge_delete(f"/sessions/{_bridge_segment(session_id)}")


@app.post("/simulations/sessions/{session_id}/actions")
def send_simulation_action(session_id: str, request: SimulationActionRequest) -> dict[str, Any]:
    return _bridge_post(f"/sessions/{_bridge_segment(session_id)}/actions", request.model_dump())


@app.get("/simulations/sessions/{session_id}/frames/latest")
def get_simulation_latest_frame(session_id: str) -> dict[str, Any]:
    return _bridge_get(f"/sessions/{_bridge_segment(session_id)}/frames/latest")


@app.get("/simulations/sessions/{session_id}/frames/stream")
def stream_simulation_frames(session_id: str, fps: float = 8.0) -> StreamingResponse:
    safe_fps = max(1.0, min(15.0, fps))
    return StreamingResponse(
        _mjpeg_frame_stream(session_id, safe_fps),
        media_type="multipart/x-mixed-replace; boundary=simopsframe",
    )


@app.post("/simulations/sessions/{session_id}/playback")
def create_simulation_playback(session_id: str, request: SimulationPlaybackRequest) -> dict[str, Any]:
    return _bridge_post(f"/sessions/{_bridge_segment(session_id)}/playback", request.model_dump(exclude_none=True))


@app.get("/simulations/native-ui")
def get_simulation_native_ui() -> dict[str, Any]:
    configured_url = os.environ.get("SIMOPS_NATIVE_SIM_UI_URL") or os.environ.get("SIMOPS_NOVNC_URL")
    commands = {
        "Xvfb": bool(shutil.which("Xvfb")),
        "xvfb-run": bool(shutil.which("xvfb-run")),
        "x11vnc": bool(shutil.which("x11vnc")),
        "websockify": bool(shutil.which("websockify")),
        "vncserver": bool(shutil.which("vncserver")),
    }
    if configured_url:
        reachable = _url_reachable(configured_url)
        return {
            "status": "available" if reachable else "configured_unreachable",
            "mode": "embedded_native_ui",
            "url": configured_url,
            "iframe_url": configured_url,
            "commands": commands,
            "note": "Embeds the configured native simulator UI endpoint.",
        }
    return {
        "status": "not_configured",
        "mode": "headless_render_stream",
        "url": "",
        "iframe_url": "",
        "commands": commands,
        "required_env": ["SIMOPS_NATIVE_SIM_UI_URL"],
        "note": "No native noVNC/UI endpoint is configured; the platform uses the real headless renderer frame stream.",
    }


def _catalog() -> dict[str, Any]:
    external_generators = {
        "infinigen": "SIMOPS_INFINIGEN_COMMAND",
        "procthor": "SIMOPS_PROCTHOR_COMMAND",
        "embodiedgen": "SIMOPS_EMBODIEDGEN_COMMAND",
    }
    external_status = {
        generator: "available" if os.environ.get(env_name) else "unconfigured"
        for generator, env_name in external_generators.items()
    }
    lerobot_python_status = "available" if _env_points_to_executable("SIMOPS_LEROBOT_PYTHON") else "requires_SIMOPS_LEROBOT_PYTHON"
    motrix_probe = motrixsim_probe()
    motrix_status = "available" if motrix_probe["ok"] else "not_configured"
    motrix_required_env = [] if motrix_probe["ok"] else motrix_probe.get("required_env", [])
    motrix_source = motrix_probe.get("source") or {}
    motrix_scene_entries = []
    for scene_id, scene in MOTRIXSIM_EXAMPLE_SCENES.items():
        scene_xml = motrixsim_scene_xml(scene_id)
        motrix_scene_entries.append(
            {
                "id": scene_id,
                "label": scene["label"],
                "label_zh": scene["label_zh"],
                "status": "available" if motrix_probe["ok"] and scene_xml and scene_xml.exists() else "not_configured",
                "simulator": "motrixsim",
                "generator": "motrixsim_examples",
                "source_path": str(scene_xml) if scene_xml else "",
                "required_env": motrix_required_env,
            }
        )
    return {
        "simulators": [
            {
                "id": "maniskill",
                "label": "ManiSkill",
                "label_zh": "ManiSkill",
                "status": "available",
                "version": "3.0.1",
                "license": "Apache-2.0",
            },
            {
                "id": "motrixsim",
                "label": "MotrixSim",
                "label_zh": "MotrixSim",
                "status": motrix_status,
                "version": motrix_probe.get("version", ""),
                "license": MOTRIXSIM_LICENSE,
                "required_env": motrix_required_env,
                "source": motrix_source,
                "detail": {
                    "python": motrix_probe.get("python"),
                    "docs": motrix_probe.get("docs"),
                    "home": motrix_probe.get("home"),
                    "step_ok": motrix_probe.get("step_ok"),
                    "error": motrix_probe.get("error"),
                },
            },
            {
                "id": "genesis_world",
                "label": "Genesis World",
                "label_zh": "Genesis World",
                "status": "unconfigured",
                "required_env": ["SIMOPS_GENESIS_PYTHON"],
            },
            {
                "id": "mujoco",
                "label": "MuJoCo",
                "label_zh": "MuJoCo",
                "status": "unconfigured",
                "required_env": ["SIMOPS_MUJOCO_PYTHON"],
            },
        ],
        "scene_generators": [
            {
                "id": "maniskill_tabletop",
                "label": "ManiSkill Tabletop",
                "label_zh": "ManiSkill 桌面场景",
                "status": "available",
            },
            {
                "id": "motrixsim_examples",
                "label": "MotrixSim Installed Examples",
                "label_zh": "MotrixSim 已安装示例导入",
                "status": motrix_status,
                "simulator": "motrixsim",
                "required_env": motrix_required_env,
            },
            *motrix_scene_entries,
            {
                "id": "robocasa_kitchen",
                "label": "RoboCasa Kitchen",
                "label_zh": "RoboCasa 厨房",
                "status": "config_available",
            },
            {
                "id": "infinigen",
                "label": "Infinigen",
                "label_zh": "Infinigen",
                "status": external_status["infinigen"],
                "required_env": ["SIMOPS_INFINIGEN_COMMAND"],
            },
            {
                "id": "procthor",
                "label": "ProcTHOR",
                "label_zh": "ProcTHOR",
                "status": external_status["procthor"],
                "required_env": ["SIMOPS_PROCTHOR_COMMAND"],
            },
            {
                "id": "embodiedgen",
                "label": "EmbodiedGen",
                "label_zh": "EmbodiedGen",
                "status": external_status["embodiedgen"],
                "required_env": ["SIMOPS_EMBODIEDGEN_COMMAND"],
            },
        ],
        "robots": [
            {
                "id": "panda",
                "label": "Franka Panda",
                "label_zh": "Franka Panda 单臂",
                "status": "available",
                "tasks": ["PickCube-v1"],
            },
            {
                "id": "motrix_body",
                "label": "MotrixSim Body Scene",
                "label_zh": "MotrixSim 基础刚体场景",
                "status": motrix_status,
                "tasks": ["MotrixSimStep"],
            },
            {
                "id": "motrix_panda",
                "label": "MotrixSim Franka Panda",
                "label_zh": "MotrixSim Franka Panda",
                "status": next(
                    (scene["status"] for scene in motrix_scene_entries if scene["id"] == "motrixsim_panda"),
                    motrix_status,
                ),
                "tasks": ["MotrixSimStep"],
            },
            {
                "id": "so100_follower",
                "label": "SO-100 Follower",
                "label_zh": "SO-100 从臂",
                "status": "deployment_target",
            },
            {"id": "ur5e", "label": "UR5e", "label_zh": "UR5e", "status": "unconfigured"},
            {"id": "aloha", "label": "ALOHA", "label_zh": "ALOHA", "status": "unconfigured"},
        ],
        "assets": [
            {"id": "cube", "label": "Cube", "label_zh": "方块", "status": "available"},
            {"id": "tabletop", "label": "Tabletop", "label_zh": "桌面", "status": "available"},
            {"id": "goal", "label": "Goal Marker", "label_zh": "目标标记", "status": "available"},
            {"id": "body", "label": "Motrix body.xml", "label_zh": "Motrix body.xml", "status": motrix_status},
            {"id": "sphere", "label": "Sphere", "label_zh": "球体", "status": motrix_status},
            {"id": "panda", "label": "Motrix Panda assets", "label_zh": "Motrix Panda 资产", "status": motrix_status},
            {"id": "drawer", "label": "Drawer", "label_zh": "抽屉", "status": "requires_robocasa"},
            {"id": "cup", "label": "Cup", "label_zh": "杯子", "status": "requires_asset_source"},
        ],
        "tasks": [
            {"id": "PickCube-v1", "label": "Pick cube to goal", "label_zh": "拿起方块到目标", "status": "available"},
            {
                "id": "MotrixSimStep",
                "label": "Load and step MotrixSim MJCF scene",
                "label_zh": "加载并步进 MotrixSim MJCF 场景",
                "status": motrix_status,
            },
            {"id": "OpenDrawer", "label": "Open drawer", "label_zh": "打开抽屉", "status": "requires_robocasa"},
            {"id": "PickCup", "label": "Pick cup", "label_zh": "拿杯子", "status": "requires_asset_source"},
            {"id": "PlaceObject", "label": "Place object", "label_zh": "放置物体", "status": "requires_asset_source"},
        ],
        "sensors": [
            {
                "id": "state_dict_rgb",
                "label": "State dict + RGB cameras",
                "label_zh": "状态字典 + RGB 相机",
                "status": "available",
            },
            {"id": "state_only", "label": "State only", "label_zh": "仅状态", "status": "available"},
            {"id": "depth_rgb", "label": "RGB-D cameras", "label_zh": "RGB-D 相机", "status": "unconfigured"},
        ],
        "randomization": [
            {"id": "object_pose", "label": "Object pose", "label_zh": "物体位姿", "status": "available"},
            {"id": "camera_pose", "label": "Camera pose", "label_zh": "相机位姿", "status": "available"},
            {"id": "lighting", "label": "Lighting", "label_zh": "光照", "status": "requires_renderer"},
            {"id": "textures", "label": "Textures", "label_zh": "纹理", "status": "requires_asset_source"},
        ],
        "data_formats": [
            {"id": "lerobot", "label": "LeRobotDataset", "label_zh": "LeRobotDataset", "status": "available"},
            {
                "id": "motrixsim_json",
                "label": "MotrixSim step JSON",
                "label_zh": "MotrixSim 步进 JSON",
                "status": motrix_status,
            },
            {
                "id": "robomimic",
                "label": "robomimic HDF5",
                "label_zh": "robomimic HDF5",
                "status": "compatible_export_planned",
            },
        ],
        "policies": [
            {"id": "act", "label": "ACT", "label_zh": "ACT", "status": "available"},
            {"id": "diffusion", "label": "Diffusion Policy", "label_zh": "Diffusion Policy", "status": "available"},
            {"id": "smolvla", "label": "SmolVLA", "label_zh": "SmolVLA", "status": "available_if_installed"},
        ],
        "dataset_operations": [
            {
                "id": "convert_to_lerobot",
                "label": "Convert ManiSkill HDF5 to LeRobot",
                "label_zh": "将 ManiSkill HDF5 转为 LeRobot",
                "status": "available",
            },
            {
                "id": "merge_lerobot",
                "label": "Merge LeRobot datasets",
                "label_zh": "合并 LeRobot 数据集",
                "status": lerobot_python_status,
                "required_env": ["SIMOPS_LEROBOT_PYTHON"],
            },
        ],
        "deployment_targets": [
            {"id": "ros2", "label": "ROS 2 bridge", "label_zh": "ROS 2 桥接", "status": "available"},
            {
                "id": "lerobot_rollout",
                "label": "LeRobot rollout",
                "label_zh": "LeRobot rollout",
                "status": "available",
            },
            {"id": "gazebo", "label": "Gazebo bridge", "label_zh": "Gazebo 桥接", "status": "unconfigured"},
        ],
        "runtime_env": _runtime_env_requirements(),
        "default_state_dir": _default_state_dir(),
        "generation": {
            "built_in": ["maniskill_tabletop", "motrixsim_examples"],
            "external_commands": external_generators,
            "configured_external": [
                generator for generator, env_name in external_generators.items() if os.environ.get(env_name)
            ],
        },
        "runtime_dependencies": _runtime_dependencies(),
        "teleop": _bridge_catalog_entry(),
        "simulation_api": {
            **_bridge_catalog_entry(),
            "bridge_contract": [
                "POST /sessions",
                "GET /sessions/{session_id}",
                "POST /sessions/{session_id}/actions",
                "GET /sessions/{session_id}/frames/latest",
                "GET /sessions/{session_id}/frames/stream",
                "POST /sessions/{session_id}/playback",
            ],
            "public_endpoints": [
                "GET /simulations/sessions",
                "POST /simulations/sessions",
                "GET /simulations/sessions/{session_id}",
                "POST /simulations/sessions/{session_id}/actions",
                "GET /simulations/sessions/{session_id}/frames/latest",
                "GET /simulations/sessions/{session_id}/frames/stream",
                "POST /simulations/sessions/{session_id}/playback",
                "DELETE /simulations/sessions/{session_id}",
            ],
            "native_ui": get_simulation_native_ui(),
        },
    }


def _default_state_dir() -> str:
    return os.environ.get("SIMOPS_STATE_DIR", ".simops")


def _runtime_env_requirements() -> list[str]:
    return [
        "SIMOPS_MANISKILL_MP_PYTHON",
        "SIMOPS_LEROBOT_PYTHON",
        "SIMOPS_LEROBOT_TRAIN",
        "SIMOPS_LEROBOT_RECORD",
    ]


def _env_points_to_executable(env_name: str) -> bool:
    value = os.environ.get(env_name, "")
    if not value:
        return False
    resolved = shutil.which(value)
    path = Path(value)
    return bool(resolved or (path.exists() and os.access(path, os.X_OK)))


def _runtime_dependencies() -> dict[str, Any]:
    project_dir = Path(os.environ.get("SIMOPS_PROJECT_DIR", "/opt/open-embodied-simops"))
    maniskill_python = Path(os.environ.get("SIMOPS_MANISKILL_MP_PYTHON", project_dir / ".maniskill-mp-venv/bin/python"))
    lerobot_python = Path(os.environ.get("SIMOPS_LEROBOT_PYTHON", project_dir / ".venv/bin/python"))
    bridge = _bridge_probe()
    native_ui = get_simulation_native_ui()
    return {
        "project_dir": str(project_dir),
        "components": [
            _python_component("maniskill", maniskill_python, "mani_skill"),
            motrixsim_runtime_component(),
            _python_component("lerobot", lerobot_python, "lerobot"),
            {
                "id": "bridge_service",
                "label": "Interactive ManiSkill bridge",
                "label_zh": "交互式 ManiSkill 仿真桥接",
                "status": "available" if bridge["ok"] else "not_configured",
                "url": _bridge_base_url(),
                "installable": True,
                "detail": bridge,
            },
            {
                "id": "native_ui",
                "label": "Native simulator UI",
                "label_zh": "原生仿真器 UI",
                "status": "available" if native_ui["status"] == "available" else "not_configured",
                "url": native_ui.get("url", ""),
                "installable": True,
                "detail": native_ui,
            },
        ],
    }


def _materialize_motrixsim_generation(request: GenerationRequest) -> dict[str, Any]:
    output_dir = _generation_output_dir(Path(request.state_dir), request.name)
    try:
        return materialize_motrixsim_generation(request, output_dir)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _python_component(component_id: str, python_path: Path, module_name: str) -> dict[str, Any]:
    exists = python_path.exists() and os.access(python_path, os.X_OK)
    version = ""
    import_ok = False
    if exists:
        completed = subprocess.run(
            [
                str(python_path),
                "-c",
                (
                    "import importlib.metadata as m, importlib; "
                    f"importlib.import_module({module_name!r}); "
                    f"print(m.version({module_name!r}))"
                ),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        import_ok = completed.returncode == 0
        version = completed.stdout.strip() if import_ok else completed.stderr.strip()[-500:]
    return {
        "id": component_id,
        "label": component_id,
        "label_zh": component_id,
        "python": str(python_path),
        "status": "available" if exists and import_ok else "not_configured",
        "executable": exists,
        "import_ok": import_ok,
        "version": version,
        "installable": True,
    }


def _materialize_maniskill_generation(request: GenerationRequest) -> dict[str, Any]:
    if request.scene != "maniskill_tabletop":
        raise HTTPException(status_code=400, detail="ManiSkill generation currently supports maniskill_tabletop only")
    if request.task != "PickCube-v1":
        raise HTTPException(status_code=400, detail="ManiSkill generation currently supports PickCube-v1 only")
    if not {"cube", "tabletop", "goal"}.issubset(set(request.assets)):
        raise HTTPException(status_code=400, detail="PickCube-v1 scene package requires cube, tabletop, and goal assets")
    if request.kind not in {"scene", "asset", "package"}:
        raise HTTPException(status_code=400, detail=f"unsupported generation kind: {request.kind}")

    output_dir = _generation_output_dir(Path(request.state_dir), request.name)
    output_dir.mkdir(parents=True, exist_ok=False)
    source = {
        "uri": "https://github.com/haosulab/ManiSkill",
        "version": "3.0.1",
        "license": "Apache-2.0",
    }
    generated_at = datetime.now(timezone.utc).isoformat()

    scene_manifest = {
        "schema_version": "simops.scene/v1",
        "name": request.name,
        "kind": "tabletop",
        "generator": request.generator,
        "simulator": "maniskill",
        "task": request.task,
        "seed": request.seed,
        "count": request.count,
        "source": source,
        "generated_at": generated_at,
    }
    assets_manifest = {
        "schema_version": "simops.assets/v1",
        "name": request.name,
        "generator": request.generator,
        "assets": [
            {
                "id": asset,
                "category": asset,
                "source": source,
                "license": source["license"],
                "version": source["version"],
            }
            for asset in request.assets
        ],
        "generated_at": generated_at,
    }

    scene_path = output_dir / "scene.simops.json"
    assets_path = output_dir / "assets.simops.json"
    scene_path.write_text(json.dumps(scene_manifest, indent=2, sort_keys=True), encoding="utf-8")
    assets_path.write_text(json.dumps(assets_manifest, indent=2, sort_keys=True), encoding="utf-8")
    scene_sha, scene_size = sha256_path(scene_path)
    assets_sha, assets_size = sha256_path(assets_path)
    preview_manifest = _build_maniskill_preview_scene(
        name=request.name,
        scene=request.scene,
        task=request.task,
        assets=request.assets,
        seed=request.seed,
        source=source,
        include_robot=False,
        generated_from=[
            {"path": str(scene_path), "sha256": scene_sha, "role": "scene_manifest"},
            {"path": str(assets_path), "sha256": assets_sha, "role": "asset_manifest"},
        ],
    )
    preview_path = output_dir / "preview_scene.simops.json"
    preview_path.write_text(json.dumps(preview_manifest, indent=2, sort_keys=True), encoding="utf-8")
    preview_sha, preview_size = sha256_path(preview_path)

    manifest = {
        "schema_version": "simops.generation/v1",
        "id": output_dir.name,
        "name": request.name,
        "status": "succeeded",
        "generator": request.generator,
        "kind": request.kind,
        "scene": request.scene,
        "assets": request.assets,
        "task": request.task,
        "seed": request.seed,
        "count": request.count,
        "output_format": request.output_format,
        "generated_at": generated_at,
        "source_components": [
            {
                "id": "maniskill",
                "kind": "scene_asset_generator",
                "source": source,
            }
        ],
        "artifacts": [
            {
                "name": "scene_manifest",
                "role": "scene_manifest",
                "path": str(scene_path),
                "sha256": scene_sha,
                "size_bytes": scene_size,
                "media_type": "application/json",
                "source": source,
            },
            {
                "name": "asset_manifest",
                "role": "asset_manifest",
                "path": str(assets_path),
                "sha256": assets_sha,
                "size_bytes": assets_size,
                "media_type": "application/json",
                "source": source,
            },
            {
                "name": "preview_scene",
                "role": "preview_scene",
                "path": str(preview_path),
                "sha256": preview_sha,
                "size_bytes": preview_size,
                "media_type": "application/json",
                "source": source,
            },
        ],
    }
    manifest_path = output_dir / "package_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    package_sha, package_size = sha256_path(output_dir)
    manifest["path"] = str(output_dir)
    manifest["sha256"] = package_sha
    manifest["size_bytes"] = package_size
    return manifest


def _run_external_generation(request: GenerationRequest) -> dict[str, Any]:
    env_map = {
        "infinigen": "SIMOPS_INFINIGEN_COMMAND",
        "procthor": "SIMOPS_PROCTHOR_COMMAND",
        "embodiedgen": "SIMOPS_EMBODIEDGEN_COMMAND",
    }
    env_name = env_map.get(request.generator)
    if not env_name:
        raise HTTPException(status_code=400, detail=f"unsupported generator: {request.generator}")

    configured_command = os.environ.get(env_name)
    if not configured_command:
        raise HTTPException(
            status_code=503,
            detail=f"{env_name} is not configured; refusing to fake {request.generator} generation",
        )

    output_dir = _generation_output_dir(Path(request.state_dir), request.name)
    output_dir.mkdir(parents=True, exist_ok=False)
    command = shlex.split(configured_command) + [
        "--output-dir",
        str(output_dir),
        "--kind",
        request.kind,
        "--seed",
        str(request.seed),
        "--count",
        str(request.count),
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    (output_dir / "generator.stdout.log").write_text(completed.stdout, encoding="utf-8")
    (output_dir / "generator.stderr.log").write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        raise HTTPException(status_code=500, detail=completed.stderr.strip() or completed.stdout.strip())

    digest, size_bytes = sha256_path(output_dir)
    manifest = {
        "schema_version": "simops.generation/v1",
        "id": output_dir.name,
        "name": request.name,
        "status": "succeeded",
        "generator": request.generator,
        "kind": request.kind,
        "seed": request.seed,
        "count": request.count,
        "path": str(output_dir),
        "sha256": digest,
        "size_bytes": size_bytes,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "command_env": env_name,
    }
    (output_dir / "package_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def _generation_output_dir(state_dir: Path, name: str) -> Path:
    generation_dir = state_dir / "generation"
    generation_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return generation_dir / f"{timestamp}-{_slug(name)}"


def _first_source(job: dict[str, Any]) -> dict[str, Any]:
    components = job.get("source_components") or []
    if components and isinstance(components[0], dict):
        return components[0].get("source") or {}
    return {}


def _preview_scene_from_generation_manifest(manifest: dict[str, Any], manifest_path: Path) -> dict[str, Any]:
    preview_artifact = next((item for item in manifest.get("artifacts", []) if item.get("role") == "preview_scene"), None)
    if preview_artifact:
        preview_path = Path(preview_artifact.get("path", ""))
        preview = _read_json_if_exists(preview_path)
        if preview:
            package_sha, package_size = sha256_path(manifest_path)
            preview["package_manifest"] = {
                "path": str(manifest_path),
                "sha256": package_sha,
                "size_bytes": package_size,
            }
            return preview

    source = _first_source(manifest) or {
        "uri": "https://github.com/haosulab/ManiSkill",
        "version": "3.0.1",
        "license": "Apache-2.0",
    }
    artifacts = []
    for artifact in manifest.get("artifacts", []):
        path = Path(artifact.get("path", ""))
        if path.exists():
            digest, _ = sha256_path(path)
        else:
            digest = artifact.get("sha256", "")
        artifacts.append({"path": str(path), "sha256": digest, "role": artifact.get("role")})
    preview = _build_maniskill_preview_scene(
        name=manifest.get("name", manifest_path.parent.name),
        scene=manifest.get("scene", "maniskill_tabletop"),
        task=manifest.get("task", "PickCube-v1"),
        assets=manifest.get("assets", []),
        seed=int(manifest.get("seed") or 0),
        source=source,
        include_robot=False,
        generated_from=artifacts,
    )
    package_sha, package_size = sha256_path(manifest_path)
    preview["package_manifest"] = {
        "path": str(manifest_path),
        "sha256": package_sha,
        "size_bytes": package_size,
    }
    return preview


def _build_maniskill_preview_scene(
    *,
    name: str,
    scene: str,
    task: str,
    assets: list[str],
    seed: int,
    source: dict[str, Any],
    include_robot: bool,
    generated_from: list[dict[str, Any]],
) -> dict[str, Any]:
    rng = random.Random(seed)
    asset_set = set(assets)
    objects: list[dict[str, Any]] = []
    if "tabletop" in asset_set or scene == "maniskill_tabletop":
        objects.append(
            _preview_object(
                "tabletop",
                "box",
                [1.2, 0.82, 0.06],
                [0.0, 0.0, -0.03],
                "#9ca8b3",
                source,
            )
        )
    if "goal" in asset_set:
        objects.append(
            _preview_object(
                "goal",
                "torus",
                [0.09, 0.006, 24],
                [0.34, 0.18, 0.012],
                "#0f8a5f",
                source,
            )
        )
    if "cube" in asset_set:
        objects.append(
            _preview_object(
                "cube",
                "box",
                [0.07, 0.07, 0.07],
                [-0.22 + rng.uniform(-0.06, 0.06), -0.08 + rng.uniform(-0.05, 0.05), 0.035],
                "#d94b32",
                source,
            )
        )
    if include_robot:
        objects.extend(_panda_preview_objects(source))

    return {
        "schema_version": "simops.preview_scene/v1",
        "name": name,
        "scene": scene,
        "task": task,
        "seed": seed,
        "units": "meters",
        "renderer": "three.js",
        "source": source,
        "generated_from": generated_from,
        "camera": {"position": [1.25, -1.35, 0.9], "target": [0.0, 0.0, 0.05]},
        "objects": objects,
    }


def _preview_object(
    object_id: str,
    geometry: str,
    size: list[float],
    position: list[float],
    color: str,
    source: dict[str, Any],
    *,
    rotation: list[float] | None = None,
) -> dict[str, Any]:
    return {
        "id": object_id,
        "geometry": geometry,
        "size": size,
        "position": position,
        "rotation": rotation or [0.0, 0.0, 0.0],
        "material": {"color": color, "roughness": 0.78, "metalness": 0.02},
        "source": source,
    }


def _panda_preview_objects(source: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        _preview_object("panda_base", "cylinder", [0.09, 0.08, 32], [-0.42, -0.31, 0.04], "#34495e", source),
        _preview_object(
            "panda_link_1",
            "box",
            [0.3, 0.045, 0.045],
            [-0.29, -0.21, 0.16],
            "#607d8b",
            source,
            rotation=[0.0, 0.0, 0.42],
        ),
        _preview_object(
            "panda_link_2",
            "box",
            [0.25, 0.04, 0.04],
            [-0.08, -0.1, 0.24],
            "#78909c",
            source,
            rotation=[0.0, 0.0, -0.25],
        ),
        _preview_object("panda_ee", "sphere", [0.035, 16, 16], [0.08, -0.16, 0.25], "#263238", source),
    ]


def _dataset_summary(path: Path, artifact: dict[str, Any] | None) -> dict[str, Any]:
    info = _read_json_if_exists(path / "meta" / "info.json")
    stats = _read_json_if_exists(path / "meta" / "stats.json")
    parquet_files = sorted(path.rglob("*.parquet")) if path.exists() else []
    data_files = [item for item in parquet_files if "/data/" in item.as_posix()]
    digest, size_bytes = sha256_path(path) if path.exists() else ("", 0)
    features = info.get("features", {}) if isinstance(info, dict) else {}
    return {
        "name": artifact.get("name") if artifact else path.name,
        "role": "lerobot_dataset",
        "path": str(path),
        "sha256": artifact.get("sha256") if artifact else digest,
        "size_bytes": artifact.get("size_bytes") if artifact else size_bytes,
        "run_id": artifact.get("run_id") if artifact else _run_id_from_path(path),
        "fps": info.get("fps") if isinstance(info, dict) else None,
        "total_frames": info.get("total_frames") if isinstance(info, dict) else None,
        "total_episodes": info.get("total_episodes") if isinstance(info, dict) else None,
        "features": [
            {"name": key, "dtype": value.get("dtype"), "shape": value.get("shape")}
            for key, value in features.items()
            if isinstance(value, dict)
        ],
        "feature_count": len(features),
        "parquet_files": len(parquet_files),
        "data_files": len(data_files),
        "has_stats": bool(stats),
        "source": "artifact" if artifact else "filesystem",
    }


def _artifact_product_summary(artifact: dict[str, Any]) -> dict[str, Any]:
    path = Path(artifact["path"])
    exists = path.exists()
    digest, size = sha256_path(path) if exists else (artifact.get("sha256", ""), artifact.get("size_bytes", 0))
    payload = {
        "name": artifact.get("name"),
        "role": artifact.get("role"),
        "run_id": artifact.get("run_id"),
        "stage_id": artifact.get("stage_id"),
        "path": artifact.get("path"),
        "sha256": digest,
        "size_bytes": size,
        "exists": exists,
        "created_at": artifact.get("created_at"),
    }
    if path.name.endswith(".json") and exists:
        payload["json"] = _read_json_if_exists(path)
    return payload


def _read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _run_id_from_path(path: Path) -> str | None:
    parts = path.parts
    if "runs" not in parts:
        return None
    index = parts.index("runs")
    if index + 1 < len(parts):
        return parts[index + 1]
    return None


def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip()).strip("-").lower() or "generated"


def _build_real_maniskill_config(request: ConfigBuildRequest) -> dict[str, Any]:
    unsupported = []
    if request.simulator != "maniskill":
        unsupported.append("simulator")
    if request.robot != "panda":
        unsupported.append("robot")
    if request.scene != "maniskill_tabletop":
        unsupported.append("scene")
    if request.task != "PickCube-v1":
        unsupported.append("task")
    if request.data_format != "lerobot":
        unsupported.append("data_format")
    if unsupported:
        raise HTTPException(
            status_code=400,
            detail=f"selected {', '.join(unsupported)} is not wired to a real local pipeline yet",
        )

    if not {"cube", "tabletop", "goal"}.issubset(set(request.assets)):
        raise HTTPException(status_code=400, detail="PickCube-v1 requires cube, tabletop, and goal assets")

    if request.policy_type not in {"act", "diffusion", "smolvla"}:
        raise HTTPException(status_code=400, detail=f"unsupported policy type: {request.policy_type}")
    if request.pipeline_mode not in {"full", "collect"}:
        raise HTTPException(status_code=400, detail=f"unsupported pipeline mode: {request.pipeline_mode}")

    normalization = _policy_normalization(request.policy_type)
    config = {
        "schema_version": "simops/v1",
        "name": request.name,
        "runtime": {"max_parallel_jobs": 1},
        "components": {
            "maniskill": {
                "kind": "simulation_data_collection",
                "source": {
                    "uri": "https://github.com/haosulab/ManiSkill",
                    "version": "3.0.1",
                    "license": "Apache-2.0",
                },
            },
            "lerobot": {
                "kind": "dataset_training_evaluation_deployment",
                "source": {
                    "uri": "https://github.com/huggingface/lerobot",
                    "version": "0.4.4",
                    "license": "Apache-2.0",
                },
            },
        },
        "pipeline": [
            {
                "id": "check_runtime",
                "adapter": "dependency_check",
                "uses": ["maniskill", "lerobot"],
                "executables": [
                    "${env:SIMOPS_MANISKILL_MP_PYTHON}",
                    "${env:SIMOPS_LEROBOT_PYTHON}",
                    "${env:SIMOPS_LEROBOT_TRAIN}",
                    "${env:SIMOPS_LEROBOT_RECORD}",
                ],
                "env_vars": _runtime_env_requirements(),
            },
            {
                "id": "collect_motionplanned_tabletop_data",
                "adapter": "command",
                "uses": ["maniskill"],
                "command": [
                    "${env:SIMOPS_MANISKILL_MP_PYTHON}",
                    "-m",
                    "mani_skill.examples.motionplanning.panda.run",
                    "-e",
                    "PickCube-v1",
                    "-n",
                    str(request.demo_episodes),
                    "-o",
                    "state_dict",
                    "--only-count-success",
                    "-b",
                    "cpu",
                    "--record-dir",
                    "${run_dir}/maniskill",
                    "--traj-name",
                    "trajectory",
                ],
                "outputs": [
                    {
                        "name": "maniskill_trajectory_h5",
                        "path": "maniskill/PickCube-v1/motionplanning/trajectory.h5",
                        "role": "trajectory_dataset",
                    },
                    {
                        "name": "maniskill_trajectory_json",
                        "path": "maniskill/PickCube-v1/motionplanning/trajectory.json",
                        "role": "trajectory_metadata",
                    },
                ],
            },
            {
                "id": "convert_to_lerobot_dataset",
                "adapter": "command",
                "uses": ["maniskill", "lerobot"],
                "command": [
                    "${env:SIMOPS_LEROBOT_PYTHON}",
                    "-m",
                    "mani_skill.trajectory.convert_to_lerobot",
                    "--traj-path",
                    "${artifacts.maniskill_trajectory_h5.path}",
                    "--output-dir",
                    "${run_dir}/datasets/lerobot_pickcube",
                    "--task-name",
                    "Pick up the cube and move it to the goal",
                    "--fps",
                    "30",
                    "--image-size",
                    "128x128",
                    "--robot-type",
                    "panda",
                ],
                "outputs": [
                    {"name": "lerobot_raw_dataset", "path": "datasets/lerobot_pickcube", "role": "lerobot_dataset"}
                ],
            },
            {
                "id": "add_task_environment_state",
                "adapter": "command",
                "uses": ["maniskill", "lerobot"],
                "command": [
                    "${env:SIMOPS_LEROBOT_PYTHON}",
                    "-m",
                    "embodied_simops.integrations.maniskill_lerobot",
                    "add-environment-state",
                    "--dataset-root",
                    "${artifacts.lerobot_raw_dataset.path}",
                    "--trajectory-h5",
                    "${artifacts.maniskill_trajectory_h5.path}",
                    "--output-root",
                    "${run_dir}/datasets/lerobot_pickcube_act",
                ],
                "outputs": [
                    {"name": "lerobot_act_dataset", "path": "datasets/lerobot_pickcube_act", "role": "lerobot_dataset"}
                ],
            },
            {
                "id": "train_policy",
                "adapter": "command",
                "uses": ["lerobot"],
                "timeout_seconds": 172800,
                "command": [
                    "${env:SIMOPS_LEROBOT_TRAIN}",
                    f"--policy.type={request.policy_type}",
                    f"--policy.normalization_mapping={normalization}",
                    f"--dataset.repo_id={request.dataset_repo_id}",
                    "--dataset.root=${artifacts.lerobot_act_dataset.path}",
                    "--policy.device=cuda",
                    "--policy.push_to_hub=false",
                    f"--steps={request.train_steps}",
                    f"--batch_size={request.batch_size}",
                    "--num_workers=0",
                    "--eval_freq=0",
                    "--log_freq=250",
                    "--save_checkpoint=true",
                    f"--save_freq={request.train_steps}",
                    "--wandb.enable=false",
                    "--output_dir=${run_dir}/training/policy",
                    "--job_name=ui_pickcube_policy",
                ],
                "outputs": [{"name": "policy_training_run", "path": "training/policy", "role": "training_run"}],
            },
            {
                "id": "select_final_policy",
                "adapter": "command",
                "uses": ["lerobot"],
                "command": [
                    "${env:SIMOPS_LEROBOT_PYTHON}",
                    "-m",
                    "embodied_simops.integrations.maniskill_lerobot",
                    "select-latest-policy",
                    "--training-dir",
                    "${artifacts.policy_training_run.path}",
                    "--output-dir",
                    "${run_dir}/training/final_policy",
                    "--manifest-path",
                    "${run_dir}/training/final_policy_manifest.json",
                ],
                "outputs": [
                    {"name": "trained_policy", "path": "training/final_policy", "role": "model"},
                    {
                        "name": "trained_policy_manifest",
                        "path": "training/final_policy_manifest.json",
                        "role": "model_manifest",
                    },
                ],
            },
            {
                "id": "evaluate_policy_in_sim",
                "adapter": "command",
                "uses": ["maniskill", "lerobot"],
                "command": [
                    "${env:SIMOPS_LEROBOT_PYTHON}",
                    "-m",
                    "embodied_simops.integrations.maniskill_lerobot",
                    "evaluate-policy",
                    "--policy-type",
                    request.policy_type,
                    "--policy-path",
                    "${artifacts.trained_policy.path}",
                    "--metrics-path",
                    "${run_dir}/evaluation/policy/metrics.json",
                    "--episodes",
                    str(request.eval_episodes),
                    "--max-steps",
                    str(request.eval_max_steps),
                    "--min-success-rate",
                    str(request.min_success_rate),
                    "--seed",
                    str(request.randomization_seed),
                    "--trajectory-h5",
                    "${artifacts.maniskill_trajectory_h5.path}",
                ],
                "outputs": [
                    {"name": "sim_eval_metrics", "path": "evaluation/policy/metrics.json", "role": "evaluation_report"}
                ],
            },
            {
                "id": "export_deployment_interfaces",
                "adapter": "deployment_export",
                "uses": ["lerobot"],
                "policy_artifact": "trained_policy",
                "output_dir": "deployment",
                "ros2": {
                    "package": "simops_policy_bridge",
                    "node": "policy_rollout_node",
                    "observation_topic": "/simops/observations",
                    "action_topic": "/simops/actions",
                },
                "lerobot": {
                    "robot_type": "so100_follower",
                    "policy_type": request.policy_type,
                    "task": "pick up the cube and move it to the goal",
                    "duration_seconds": 30,
                    "robot_port": "$SIMOPS_ROBOT_PORT",
                },
                "outputs": [
                    {
                        "name": "ros2_rollout_node",
                        "path": "deployment/ros2/policy_rollout_node.py",
                        "role": "deployment_interface",
                    },
                    {
                        "name": "lerobot_rollout",
                        "path": "deployment/lerobot/rollout.py",
                        "role": "deployment_interface",
                    },
                ],
            },
        ],
        "stack": {
            "simulator": {"component": request.simulator},
            "robot": {"name": request.robot, "embodiment": "single_arm"},
            "scene": {"generator": request.simulator, "kind": "tabletop"},
            "assets": [{"component": request.simulator, "categories": request.assets}],
            "task": {"id": request.task, "language": "pick up the cube and move it to the goal"},
            "sensors": _sensor_stack(request.sensor_preset),
            "randomization": {"seed": request.randomization_seed, "domains": request.randomization_domains},
            "data_format": {"name": request.data_format, "compatible_with": ["robomimic"]},
            "training_strategy": {"policy": request.policy_type, "device": "cuda", "steps": request.train_steps},
            "deployment_targets": request.deployment_targets,
        },
    }

    if request.pipeline_mode == "collect":
        config["pipeline"] = config["pipeline"][:2]
        config["stack"]["training_strategy"]["steps"] = 0

    return config


def _sensor_stack(sensor_preset: str) -> dict[str, Any]:
    if sensor_preset == "state_only":
        return {"cameras": [], "proprioception": True}
    if sensor_preset == "state_dict_rgb":
        return {
            "cameras": [{"name": "base_camera", "width": 640, "height": 480}],
            "proprioception": True,
        }
    raise HTTPException(status_code=400, detail=f"unsupported sensor preset: {sensor_preset}")


def _policy_normalization(policy_type: str) -> str:
    if policy_type == "act":
        return "{VISUAL: MEAN_STD, STATE: MEAN_STD, ACTION: MEAN_STD, ENV: MEAN_STD}"
    if policy_type in {"diffusion", "smolvla"}:
        return "{VISUAL: MEAN_STD, STATE: MIN_MAX, ACTION: MIN_MAX, ENV: MIN_MAX}"
    raise HTTPException(status_code=400, detail=f"unsupported policy type: {policy_type}")


def _unique_config_path(config_dir: Path, name: str) -> Path:
    base = re.sub(r"[^a-zA-Z0-9_.-]+", "-", name.strip()).strip("-").lower() or "simops-task"
    candidate = config_dir / f"{base}.yaml"
    index = 2
    while candidate.exists():
        candidate = config_dir / f"{base}-{index}.yaml"
        index += 1
    return candidate


def _bridge_post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _bridge_request(path, method="POST", payload=payload)


def _bridge_get(path: str) -> dict[str, Any]:
    return _bridge_request(path, method="GET", payload=None)


def _bridge_delete(path: str) -> dict[str, Any]:
    return _bridge_request(path, method="DELETE", payload=None)


def _bridge_base_url() -> str:
    return os.environ.get("SIMOPS_TELEOP_BRIDGE_URL") or os.environ.get(
        "SIMOPS_DEFAULT_TELEOP_BRIDGE_URL",
        "http://127.0.0.1:18082",
    )


def _bridge_catalog_entry() -> dict[str, Any]:
    probe = _bridge_probe()
    return {
        "status": "available" if probe["ok"] else "not_configured",
        "url": _bridge_base_url(),
        "required_env": [] if probe["ok"] else ["SIMOPS_TELEOP_BRIDGE_URL or managed simops-bridge.service"],
        "detail": probe,
    }


def _bridge_probe() -> dict[str, Any]:
    base_url = _bridge_base_url()
    request = urllib.request.Request(base_url.rstrip("/") + "/health", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=1.5) as response:
            body = response.read().decode("utf-8")
    except OSError as exc:
        return {"ok": False, "url": base_url, "error": str(exc)}
    try:
        payload = json.loads(body) if body else {}
    except json.JSONDecodeError:
        payload = {"body": body}
    return {"ok": 200 <= response.status < 300, "url": base_url, "response": payload}


def _bridge_request(path: str, *, method: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    base_url = _bridge_base_url()
    url = base_url.rstrip("/") + path
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method=method)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8") or str(exc)
        raise HTTPException(status_code=exc.code, detail=detail) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                f"managed simulation bridge is not reachable at {base_url}; "
                "install/start simops-bridge.service or set SIMOPS_TELEOP_BRIDGE_URL to a real bridge"
            ),
        ) from exc
    return json.loads(body) if body else {"status": "ok"}


def _mjpeg_frame_stream(session_id: str, fps: float):
    interval = 1.0 / fps
    while True:
        payload = _bridge_get(f"/sessions/{_bridge_segment(session_id)}/frames/latest")
        frame = payload.get("frame") or {}
        image = _frame_image_bytes(frame)
        if image is None:
            time.sleep(interval)
            continue
        yield (
            b"--simopsframe\r\n"
            + f"Content-Type: {frame.get('media_type', 'image/png')}\r\n".encode("ascii")
            + f"Content-Length: {len(image)}\r\n".encode("ascii")
            + f"X-SimOps-Step: {frame.get('step', payload.get('step', 0))}\r\n".encode("ascii")
            + f"X-SimOps-SHA256: {frame.get('sha256', '')}\r\n\r\n".encode("ascii")
            + image
            + b"\r\n"
        )
        time.sleep(interval)


def _frame_image_bytes(frame: dict[str, Any]) -> bytes | None:
    if not str(frame.get("media_type", "")).startswith("image/"):
        return None
    if frame.get("encoding") != "base64" or not frame.get("data_base64"):
        return None
    try:
        return base64.b64decode(frame["data_base64"])
    except (ValueError, TypeError):
        return None


def _url_reachable(url: str) -> bool:
    try:
        request = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(request, timeout=1.5) as response:
            return 200 <= response.status < 500
    except OSError:
        return False


def _bridge_segment(value: str) -> str:
    return urllib.parse.quote(value, safe="")


@contextmanager
def _temporary_env(overrides: dict[str, str]):
    original: dict[str, str | None] = {}
    try:
        for key, value in overrides.items():
            original[key] = os.environ.get(key)
            os.environ[key] = value
        yield
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
