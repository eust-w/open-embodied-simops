from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MOTRIXSIM_SOURCE_URI = "https://github.com/Motphys/motrixsim-docs"
# The docs license does not establish the license of the installed engine/assets.
MOTRIXSIM_LICENSE = "NOASSERTION"
MOTRIXSIM_LICENSE_URL = "https://motphys.com/en/motrixsim"
MOTRIXSIM_EXAMPLE_SCENES: dict[str, dict[str, Any]] = {
    "motrixsim_body": {
        "label": "MotrixSim body.xml",
        "label_zh": "MotrixSim body.xml 基础刚体场景",
        "relative_xml": "examples/assets/body.xml",
        "robot": "motrix_body",
        "assets": ["body", "cube", "sphere"],
    },
    "motrixsim_panda": {
        "label": "MotrixSim Franka Panda",
        "label_zh": "MotrixSim Franka Panda 机械臂场景",
        "relative_xml": "examples/assets/franka_emika_panda/scene.xml",
        "robot": "motrix_panda",
        "assets": ["panda", "floor"],
    },
}


def motrixsim_probe(scene_id: str = "motrixsim_body", *, run_step: bool = True) -> dict[str, Any]:
    python = _motrixsim_python_path()
    docs = _motrixsim_docs_path()
    home = _motrixsim_home_path()
    scene_xml = motrixsim_scene_xml(scene_id)
    required_env = [
        "SIMOPS_MOTRIXSIM_PYTHON",
        "SIMOPS_MOTRIXSIM_DOCS",
        "SIMOPS_MOTRIXSIM_HOME",
    ]

    base = {
        "ok": False,
        "python": str(python) if python else "",
        "docs": str(docs),
        "home": str(home),
        "scene_xml": str(scene_xml) if scene_xml else "",
        "source": _motrixsim_source(version=""),
        "required_env": required_env,
        "step_ok": False,
    }
    if not python or not python.exists() or not os.access(python, os.X_OK):
        return base | {"error": "MotrixSim Python executable was not found"}
    if not scene_xml or not scene_xml.exists():
        return base | {"error": f"MotrixSim example scene was not found: {scene_id}"}

    code = _probe_script(str(scene_xml), steps=1 if run_step else 0)
    completed = _run_with_motrixsim_python(python, code, cwd=scene_xml.parent, timeout=20)
    payload = _last_json_line(completed.stdout)
    if completed.returncode != 0:
        return base | {
            "error": completed.stderr.strip()[-1000:] or completed.stdout.strip()[-1000:],
            "returncode": completed.returncode,
        }
    if not payload:
        return base | {"error": "MotrixSim probe did not emit JSON", "stdout": completed.stdout[-1000:]}

    version = str(payload.get("version") or "")
    return base | payload | {
        "ok": bool(payload.get("import_ok") and (payload.get("step_ok") or not run_step)),
        "version": version,
        "source": _motrixsim_source(version=version),
        "commit": _git_commit(docs),
    }


def motrixsim_runtime_component() -> dict[str, Any]:
    probe = motrixsim_probe()
    return {
        "id": "motrixsim",
        "label": "MotrixSim",
        "label_zh": "MotrixSim",
        "python": probe.get("python", ""),
        "status": "available" if probe["ok"] else "not_configured",
        "executable": bool(probe.get("python")),
        "import_ok": bool(probe.get("import_ok")),
        "step_ok": bool(probe.get("step_ok")),
        "version": probe.get("version", ""),
        "license": MOTRIXSIM_LICENSE,
        "installable": False,
        "detail": probe,
    }


def motrixsim_scene_xml(scene_id: str) -> Path | None:
    scene = MOTRIXSIM_EXAMPLE_SCENES.get(scene_id)
    if not scene:
        return None
    return _motrixsim_docs_path() / scene["relative_xml"]


def motrixsim_python_path() -> Path | None:
    return _motrixsim_python_path()


def motrixsim_source() -> dict[str, Any]:
    probe = motrixsim_probe(run_step=False)
    return probe.get("source") or _motrixsim_source(version=probe.get("version", ""))


def materialize_motrixsim_generation(request: Any, output_dir: Path) -> dict[str, Any]:
    from embodied_simops.provenance import sha256_path

    if request.kind not in {"scene", "asset", "package"}:
        raise ValueError(f"unsupported generation kind: {request.kind}")
    if request.task != "MotrixSimStep":
        raise ValueError("MotrixSim generation currently supports MotrixSimStep only")

    source_xml = motrixsim_scene_xml(request.scene)
    if not source_xml:
        raise ValueError(f"unsupported MotrixSim scene: {request.scene}")
    if not source_xml.exists():
        raise RuntimeError(f"MotrixSim source scene does not exist: {source_xml}")

    probe = motrixsim_probe(request.scene)
    if not probe["ok"]:
        raise RuntimeError(f"MotrixSim is not available: {probe.get('error')}")

    output_dir.mkdir(parents=True, exist_ok=False)
    package_scene_xml = _copy_scene_package(source_xml, output_dir)
    validation = validate_motrixsim_scene(package_scene_xml, steps=max(1, min(request.count, 10)))
    generated_at = datetime.now(timezone.utc).isoformat()
    source = _motrixsim_source(version=str(probe.get("version") or ""), commit=probe.get("commit"))

    scene_manifest = {
        "schema_version": "simops.scene/v1",
        "name": request.name,
        "kind": "motrixsim_mjcf",
        "generator": request.generator,
        "simulator": "motrixsim",
        "scene": request.scene,
        "task": request.task,
        "seed": request.seed,
        "source": source,
        "source_xml": str(source_xml),
        "package_xml": str(package_scene_xml),
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
    preview_manifest = build_motrixsim_preview_scene(
        name=request.name,
        scene=request.scene,
        task=request.task,
        assets=request.assets,
        seed=request.seed,
        source=source,
        scene_xml=package_scene_xml,
        generated_from=[],
    )

    scene_path = output_dir / "scene.simops.json"
    assets_path = output_dir / "assets.simops.json"
    validation_path = output_dir / "motrix_validation.json"
    preview_path = output_dir / "preview_scene.simops.json"
    scene_path.write_text(json.dumps(scene_manifest, indent=2, sort_keys=True), encoding="utf-8")
    assets_path.write_text(json.dumps(assets_manifest, indent=2, sort_keys=True), encoding="utf-8")
    validation_path.write_text(json.dumps(validation, indent=2, sort_keys=True), encoding="utf-8")
    preview_path.write_text(json.dumps(preview_manifest, indent=2, sort_keys=True), encoding="utf-8")

    artifacts = []
    for name, role, path in [
        ("motrix_scene_xml", "motrix_scene_xml", package_scene_xml),
        ("scene_manifest", "scene_manifest", scene_path),
        ("asset_manifest", "asset_manifest", assets_path),
        ("motrix_validation", "motrix_validation", validation_path),
        ("preview_scene", "preview_scene", preview_path),
    ]:
        digest, size = sha256_path(path)
        artifacts.append(
            {
                "name": name,
                "role": role,
                "path": str(path),
                "sha256": digest,
                "size_bytes": size,
                "media_type": "application/json" if path.suffix == ".json" else "application/xml",
                "source": source,
            }
        )

    manifest = {
        "schema_version": "simops.generation/v1",
        "id": output_dir.name,
        "name": request.name,
        "status": "succeeded",
        "generator": request.generator,
        "simulator": "motrixsim",
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
                "id": "motrixsim",
                "kind": "simulation_engine_and_example_assets",
                "source": source,
            }
        ],
        "artifacts": artifacts,
        "validation": validation,
    }
    manifest_path = output_dir / "package_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    package_sha, package_size = sha256_path(output_dir)
    manifest["path"] = str(output_dir)
    manifest["sha256"] = package_sha
    manifest["size_bytes"] = package_size
    return manifest


def validate_motrixsim_scene(scene_xml: Path, *, steps: int) -> dict[str, Any]:
    python = _motrixsim_python_path()
    if not python or not python.exists():
        raise RuntimeError("MotrixSim Python executable was not found")
    completed = _run_with_motrixsim_python(python, _probe_script(str(scene_xml), steps=steps), cwd=scene_xml.parent, timeout=30)
    payload = _last_json_line(completed.stdout)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    if not payload:
        raise RuntimeError("MotrixSim validation did not emit JSON")
    payload["scene_xml"] = str(scene_xml)
    payload["validated_at"] = datetime.now(timezone.utc).isoformat()
    return payload


def build_motrixsim_preview_scene(
    *,
    name: str,
    scene: str,
    task: str,
    assets: list[str],
    seed: int,
    source: dict[str, Any] | None = None,
    scene_xml: Path | None = None,
    generated_from: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    xml_path = scene_xml or motrixsim_scene_xml(scene)
    if not xml_path or not xml_path.exists():
        raise RuntimeError(f"MotrixSim preview source scene does not exist: {scene}")
    preview_source = source or motrixsim_source()
    objects = _preview_objects_from_mjcf(xml_path, preview_source)
    if not objects:
        objects = [_preview_object("motrix_scene", "box", [0.12, 0.12, 0.12], [0.0, 0.0, 0.06], "#607d8b", preview_source)]
    return {
        "schema_version": "simops.preview_scene/v1",
        "name": name,
        "scene": scene,
        "task": task,
        "seed": seed,
        "units": "meters",
        "renderer": "three.js",
        "source": preview_source,
        "assets": assets,
        "scene_xml": str(xml_path),
        "generated_from": generated_from or [],
        "camera": {"position": [2.2, -2.4, 1.55], "target": [0.0, 0.0, 0.35]},
        "objects": objects[:200],
    }


def _motrixsim_python_path() -> Path | None:
    candidates = []
    env_value = os.environ.get("SIMOPS_MOTRIXSIM_PYTHON")
    if env_value:
        candidates.append(Path(env_value))
    candidates.extend(
        [
            _motrixsim_home_path() / ".venv/bin/python",
            _motrixsim_docs_path() / ".venv/bin/python",
        ]
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return Path(env_value) if env_value else None


def _motrixsim_home_path() -> Path:
    return Path(os.environ.get("SIMOPS_MOTRIXSIM_HOME", "/opt/Motphys/MotrixLab")).expanduser()


def _motrixsim_docs_path() -> Path:
    return Path(os.environ.get("SIMOPS_MOTRIXSIM_DOCS", "/opt/Motphys/motrixsim-docs")).expanduser()


def _run_with_motrixsim_python(
    python: Path,
    code: str,
    *,
    cwd: Path | None,
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    pythonpath_parts = []
    configured_pythonpath = os.environ.get("SIMOPS_MOTRIXSIM_PYTHONPATH")
    if configured_pythonpath:
        pythonpath_parts.append(configured_pythonpath)
    existing_pythonpath = env.get("PYTHONPATH")
    if existing_pythonpath:
        pythonpath_parts.append(existing_pythonpath)
    if pythonpath_parts:
        env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    return subprocess.run(
        [str(python), "-c", code],
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _probe_script(scene_xml: str, *, steps: int) -> str:
    return f"""
import importlib
import json

payload = {{"import_ok": False, "step_ok": False, "version": ""}}

def _jsonable(value):
    if hasattr(value, "tolist"):
        return value.tolist()
    if isinstance(value, (list, tuple)):
        return list(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)

try:
    mx = importlib.import_module("motrixsim")
    payload["import_ok"] = True
    payload["version"] = getattr(mx, "__version__", "") or ""
    if not payload["version"]:
        try:
            import importlib.metadata as metadata
            payload["version"] = metadata.version("motrixsim")
        except Exception:
            payload["version"] = ""
    model = mx.load_model({scene_xml!r})
    data = mx.SceneData(model)
    for _ in range({steps!r}):
        if hasattr(mx, "step"):
            mx.step(model, data)
        else:
            model.step(data)
    payload.update({{
        "step_ok": True,
        "model_type": type(model).__name__,
        "data_type": type(data).__name__,
        "num_geoms": getattr(model, "num_geoms", None),
        "geom_names": list(getattr(model, "geom_names", []) or [])[:50],
        "state": {{
            name: _jsonable(getattr(data, name))
            for name in ("dof_pos", "dof_vel", "actuator_ctrls")
            if hasattr(data, name)
        }},
    }})
except Exception as exc:
    payload["error"] = f"{{type(exc).__name__}}: {{exc}}"

print(json.dumps(payload, sort_keys=True))
"""


def _last_json_line(text: str) -> dict[str, Any]:
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def _copy_scene_package(source_xml: Path, output_dir: Path) -> Path:
    package_dir = output_dir / "motrixsim"
    package_dir.mkdir(parents=True, exist_ok=True)
    scene_id = _scene_id_for_xml(source_xml)
    if scene_id == "motrixsim_body":
        target = package_dir / source_xml.name
        shutil.copy2(source_xml, target)
        return target

    target_dir = package_dir / source_xml.parent.name
    shutil.copytree(source_xml.parent, target_dir)
    return target_dir / source_xml.name


def _scene_id_for_xml(source_xml: Path) -> str:
    docs = _motrixsim_docs_path()
    try:
        relative = source_xml.relative_to(docs).as_posix()
    except ValueError:
        relative = source_xml.as_posix()
    for scene_id, scene in MOTRIXSIM_EXAMPLE_SCENES.items():
        if scene["relative_xml"] == relative:
            return scene_id
    return source_xml.stem


def _preview_objects_from_mjcf(xml_path: Path, source: dict[str, Any]) -> list[dict[str, Any]]:
    root = ET.parse(xml_path).getroot()
    worldbody = root.find("worldbody")
    if worldbody is None:
        return []
    objects: list[dict[str, Any]] = []
    _collect_preview_objects(worldbody, [0.0, 0.0, 0.0], objects, source)
    return objects


def _collect_preview_objects(node: ET.Element, parent_pos: list[float], objects: list[dict[str, Any]], source: dict[str, Any]) -> None:
    for child in list(node):
        if child.tag == "body":
            body_pos = _vec(child.get("pos"), [0.0, 0.0, 0.0], length=3)
            absolute = [parent_pos[index] + body_pos[index] for index in range(3)]
            _collect_preview_objects(child, absolute, objects, source)
        elif child.tag == "geom":
            object_id = child.get("name") or f"geom_{len(objects) + 1}"
            geom_type = child.get("type", "box")
            geom_pos = _vec(child.get("pos"), [0.0, 0.0, 0.0], length=3)
            position = [parent_pos[index] + geom_pos[index] for index in range(3)]
            size = _mjcf_size(geom_type, child.get("size"))
            geometry = _mjcf_geometry(geom_type)
            color = _rgba_to_hex(child.get("rgba"))
            if geom_type == "plane":
                position[2] -= size[2] / 2
            objects.append(_preview_object(object_id, geometry, size, position, color, source))


def _mjcf_geometry(geom_type: str) -> str:
    if geom_type in {"sphere", "ellipsoid"}:
        return "sphere"
    if geom_type in {"cylinder", "capsule"}:
        return "cylinder"
    return "box"


def _mjcf_size(geom_type: str, value: str | None) -> list[float]:
    numbers = _vec(value, [0.08, 0.08, 0.08], length=3)
    if geom_type == "plane":
        return [max(numbers[0] * 2, 1.4), max(numbers[1] * 2, 1.4), 0.02]
    if geom_type == "box":
        return [max(numbers[0] * 2, 0.02), max(numbers[1] * 2, 0.02), max(numbers[2] * 2, 0.02)]
    if geom_type in {"sphere", "ellipsoid"}:
        return [max(numbers[0], 0.02), 24, 16]
    if geom_type in {"cylinder", "capsule"}:
        radius = max(numbers[0], 0.02)
        height = max(numbers[1] * 2 if numbers[1] else radius * 2, 0.04)
        return [radius, height, 32]
    return [0.08, 0.08, 0.08]


def _vec(value: str | None, default: list[float], *, length: int) -> list[float]:
    if not value:
        return list(default)
    try:
        numbers = [float(item) for item in value.replace(",", " ").split()]
    except ValueError:
        return list(default)
    if len(numbers) < length:
        numbers.extend(default[len(numbers) : length])
    return numbers[:length]


def _rgba_to_hex(value: str | None) -> str:
    rgba = _vec(value, [0.45, 0.55, 0.62, 1.0], length=4)
    channels = [max(0, min(255, round(channel * 255))) for channel in rgba[:3]]
    return "#" + "".join(f"{channel:02x}" for channel in channels)


def _preview_object(
    object_id: str,
    geometry: str,
    size: list[float],
    position: list[float],
    color: str,
    source: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": object_id,
        "geometry": geometry,
        "size": size,
        "position": position,
        "rotation": [0.0, 0.0, 0.0],
        "material": {"color": color, "roughness": 0.78, "metalness": 0.02},
        "source": source,
    }


def _motrixsim_source(*, version: str, commit: str | None = None) -> dict[str, Any]:
    source = {
        "uri": MOTRIXSIM_SOURCE_URI,
        "version": version or "unknown",
        "license": MOTRIXSIM_LICENSE,
        "license_url": MOTRIXSIM_LICENSE_URL,
        "license_status": "requires_installed_version_and_asset_review",
    }
    if commit:
        source["commit"] = commit
    return source


def _git_commit(path: Path) -> str | None:
    if not (path / ".git").exists():
        return None
    completed = subprocess.run(
        ["git", "-c", "safe.directory=*", "-C", str(path), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def _capture_cli(argv: list[str]) -> int:
    import argparse

    if argv and argv[0] == "bridge-worker":
        return _bridge_worker_cli(argv[1:])

    parser = argparse.ArgumentParser(description="Run a real MotrixSim load/step capture.")
    parser.add_argument("capture", nargs="?")
    parser.add_argument("--scene-xml", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--steps", type=int, default=10)
    args = parser.parse_args(argv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = validate_motrixsim_scene(Path(args.scene_xml), steps=args.steps)
    output = output_dir / "motrixsim_capture.json"
    output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"status": "succeeded", "path": str(output), "steps": args.steps}, sort_keys=True))
    return 0


def _bridge_worker_cli(argv: list[str]) -> int:
    import argparse
    import importlib

    parser = argparse.ArgumentParser(description="MotrixSim JSON-lines bridge worker.")
    parser.add_argument("--scene-id", required=True)
    parser.add_argument("--scene-xml", required=True)
    parser.add_argument("--assets-json", default="[]")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--render-width", type=int, default=640)
    parser.add_argument("--render-height", type=int, default=480)
    args = parser.parse_args(argv)

    scene_xml = Path(args.scene_xml)
    assets = json.loads(args.assets_json)
    mx = importlib.import_module("motrixsim")
    version = getattr(mx, "__version__", "") or _metadata_version("motrixsim")
    model = mx.load_model(str(scene_xml))
    data = mx.SceneData(model)
    renderer = _start_headless_renderer(model, args.render_width, args.render_height)
    source = _motrixsim_source(version=version)
    base_preview = build_motrixsim_preview_scene(
        name=f"motrixsim-{args.scene_id}",
        scene=args.scene_id,
        task="MotrixSimStep",
        assets=assets,
        seed=args.seed,
        source=source,
        scene_xml=scene_xml,
        generated_from=[],
    )
    state = {
        "step_count": 0,
        "last_info": {
            "model_type": type(model).__name__,
            "data_type": type(data).__name__,
            "version": version,
        },
    }

    def send(payload: dict[str, Any]) -> None:
        print(json.dumps(payload, sort_keys=True), flush=True)

    send(_worker_status(args.scene_id, assets, model, data, base_preview, state, renderer))
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            command = request.get("command", "status")
            if command == "close":
                send({"status": "closed"})
                return 0
            if command == "action":
                action = str(request.get("action", "stop"))
                velocity = float(request.get("velocity", 0.25))
                steps = int(request.get("steps", 5))
                state["last_info"] = _apply_motrixsim_action(mx, model, data, action, velocity, steps)
                state["step_count"] += 1
                send(_worker_status(args.scene_id, assets, model, data, base_preview, state, renderer))
                continue
            if command in {"status", "latest_frame"}:
                send(_worker_status(args.scene_id, assets, model, data, base_preview, state, renderer))
                continue
            send({"status": "failed", "detail": f"unknown worker command: {command}"})
        except Exception as exc:
            send({"status": "failed", "detail": f"{type(exc).__name__}: {exc}"})
    return 0


def _worker_status(
    scene_id: str,
    assets: list[str],
    model: Any,
    data: Any,
    base_preview: dict[str, Any],
    state: dict[str, Any],
    renderer: Any | None,
) -> dict[str, Any]:
    frame = _motrixsim_preview_frame(base_preview, model, data, state["step_count"], renderer)
    return {
        "status": "running",
        "simulator": "motrixsim",
        "scene": scene_id,
        "assets": assets,
        "step": state["step_count"],
        "last_info": state["last_info"],
        "state": _motrixsim_state(model, data),
        "frame": frame,
    }


def _apply_motrixsim_action(mx: Any, model: Any, data: Any, action: str, velocity: float, steps: int) -> dict[str, Any]:
    magnitude = max(0.0, min(1.0, velocity))
    if hasattr(data, "actuator_ctrls") and len(getattr(data, "actuator_ctrls")):
        ctrl = [0.0 for _ in range(len(data.actuator_ctrls))]
        mapping = {
            "forward": (0, magnitude),
            "backward": (0, -magnitude),
            "left": (1, magnitude),
            "right": (1, -magnitude),
            "lift": (2, magnitude),
            "lower": (2, -magnitude),
            "gripper_open": (-1, magnitude),
            "gripper_close": (-1, -magnitude),
            "stop": (0, 0.0),
        }
        if action not in mapping:
            raise ValueError(f"unsupported action: {action}")
        index, value = mapping[action]
        if ctrl:
            ctrl[index] = value
        data.actuator_ctrls[:] = ctrl
    elif hasattr(data, "dof_vel") and len(getattr(data, "dof_vel")):
        dof_vel = [0.0 for _ in range(len(data.dof_vel))]
        mapping = {
            "forward": (0, magnitude),
            "backward": (0, -magnitude),
            "left": (1, magnitude),
            "right": (1, -magnitude),
            "lift": (2, magnitude),
            "lower": (2, -magnitude),
            "gripper_open": (0, 0.0),
            "gripper_close": (0, 0.0),
            "stop": (0, 0.0),
        }
        if action not in mapping:
            raise ValueError(f"unsupported action: {action}")
        index, value = mapping[action]
        if dof_vel:
            dof_vel[index] = value
        if hasattr(data, "set_dof_vel"):
            try:
                data.set_dof_vel(dof_vel)
            except TypeError:
                import numpy as np

                data.set_dof_vel(np.array(dof_vel, dtype=getattr(data.dof_vel, "dtype", None)))
        else:
            data.dof_vel[:] = dof_vel
    else:
        if action != "stop":
            raise ValueError("MotrixSim scene has no actuator_ctrls or dof_vel to control")

    for _ in range(max(1, min(steps, 60))):
        if hasattr(mx, "step"):
            mx.step(model, data)
        else:
            model.step(data)
    return {"action": action, "velocity": magnitude, "substeps": max(1, min(steps, 60))}


def _motrixsim_preview_frame(
    base_preview: dict[str, Any],
    model: Any,
    data: Any,
    step_count: int,
    renderer: Any | None,
) -> dict[str, Any]:
    descriptor = json.loads(json.dumps(base_preview))
    descriptor["state"] = _motrixsim_state(model, data)
    descriptor["step"] = step_count
    if hasattr(data, "dof_pos") and len(getattr(data, "dof_pos")) >= 3:
        cube_position = [float(value) for value in data.dof_pos[:3]]
        for item in descriptor.get("objects", []):
            if item.get("id") in {"cube", "free_cube"}:
                item["position"] = cube_position
                break
    rendered = _capture_headless_frame(renderer, data, descriptor, step_count)
    if rendered:
        return rendered
    payload = json.dumps(descriptor, sort_keys=True).encode("utf-8")
    return {
        "media_type": "application/vnd.simops.preview_scene+json",
        "encoding": "json",
        "preview_scene": descriptor,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size_bytes": len(payload),
        "step": step_count,
    }


def _start_headless_renderer(model: Any, width: int, height: int) -> Any | None:
    cameras = list(getattr(model, "cameras", []) or [])
    if not cameras:
        return None
    try:
        from motrixsim.render import RenderApp

        cameras[0].set_render_target("image", max(64, width), max(64, height))
        renderer = RenderApp(headless=True)
        renderer.launch(model)
        return renderer
    except Exception:
        return None


def _capture_headless_frame(renderer: Any | None, data: Any, descriptor: dict[str, Any], step_count: int) -> dict[str, Any] | None:
    if renderer is None:
        return None
    try:
        camera = renderer.get_camera(0)
        rendered: tuple[Any, bytes] | None = None
        for attempt in range(3):
            image = _capture_headless_image(renderer, camera, data)
            if image is None or getattr(image, "pixels", None) is None:
                continue
            pixels = image.pixels
            png = _encode_rgb_png(pixels)
            rendered = (pixels, png)
            if _frame_has_visual_detail(pixels) or attempt == 2:
                break
            time.sleep(0.03)
        if rendered is None:
            return None
        pixels, png = rendered
        return {
            "media_type": "image/png",
            "encoding": "base64",
            "data_base64": base64.b64encode(png).decode("ascii"),
            "width": _pixels_width(pixels),
            "height": _pixels_height(pixels),
            "sha256": hashlib.sha256(png).hexdigest(),
            "size_bytes": len(png),
            "step": step_count,
            "preview_scene": descriptor,
            "render_source": "motrixsim.headless",
        }
    except Exception:
        return None


def _capture_headless_image(renderer: Any, camera: Any, data: Any) -> Any | None:
    renderer.sync(data)
    capture = camera.capture()
    deadline = time.monotonic() + 2.0
    while str(getattr(capture, "state", "")).lower() in {"pending", "running"} and time.monotonic() < deadline:
        renderer.sync(data)
        time.sleep(0.005)
    return capture.take_image()


def _encode_rgb_png(pixels: Any) -> bytes:
    width = _pixels_width(pixels)
    height = _pixels_height(pixels)
    rows = []
    for y in range(height):
        row = pixels[y]
        rows.append(b"\x00" + _row_rgb_bytes(row, width))
    raw = b"".join(rows)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(raw))
        + _png_chunk(b"IEND", b"")
    )


def _row_rgb_bytes(row: Any, width: int) -> bytes:
    if hasattr(row, "shape") and len(getattr(row, "shape", ())) == 2 and row.shape[1] >= 3:
        return bytes(int(channel) & 0xFF for pixel in row[:width] for channel in pixel[:3])
    return bytes(int(channel) & 0xFF for pixel in list(row)[:width] for channel in list(pixel)[:3])


def _frame_has_visual_detail(pixels: Any) -> bool:
    width = _pixels_width(pixels)
    height = _pixels_height(pixels)
    if width <= 0 or height <= 0:
        return False
    samples: set[tuple[int, int, int]] = set()
    step_x = max(1, width // 16)
    step_y = max(1, height // 12)
    for y in range(0, height, step_y):
        row = pixels[y]
        for x in range(0, width, step_x):
            pixel = row[x]
            samples.add(tuple(int(channel) & 0xFF for channel in list(pixel)[:3]))
            if len(samples) >= 4:
                return True
    return False


def _pixels_width(pixels: Any) -> int:
    shape = getattr(pixels, "shape", None)
    if shape is not None and len(shape) >= 2:
        return int(shape[1])
    return len(pixels[0])


def _pixels_height(pixels: Any) -> int:
    shape = getattr(pixels, "shape", None)
    if shape is not None and len(shape) >= 2:
        return int(shape[0])
    return len(pixels)


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)


def _motrixsim_state(model: Any, data: Any) -> dict[str, Any]:
    return {
        "model_type": type(model).__name__,
        "data_type": type(data).__name__,
        "num_geoms": getattr(model, "num_geoms", None),
        "num_dof_pos": getattr(model, "num_dof_pos", None),
        "num_dof_vel": getattr(model, "num_dof_vel", None),
        "num_actuators": getattr(model, "num_actuators", None),
        "geom_names": _jsonable(list(getattr(model, "geom_names", []) or [])[:50]),
        "dof_pos": _jsonable(getattr(data, "dof_pos", [])),
        "dof_vel": _jsonable(getattr(data, "dof_vel", [])),
        "actuator_ctrls": _jsonable(getattr(data, "actuator_ctrls", [])),
    }


def _jsonable(value: Any) -> Any:
    if hasattr(value, "tolist"):
        return value.tolist()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _metadata_version(package: str) -> str:
    try:
        import importlib.metadata as metadata

        return metadata.version(package)
    except Exception:
        return ""


def main() -> None:
    raise SystemExit(_capture_cli(sys.argv[1:]))


if __name__ == "__main__":
    main()
