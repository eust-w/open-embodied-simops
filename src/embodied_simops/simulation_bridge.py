from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import select
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from embodied_simops.integrations.motrixsim import motrixsim_python_path, motrixsim_scene_xml


@dataclass
class SimulationSession:
    session_id: str
    request: dict[str, Any]
    simulator: str
    created_at: float
    env: Any | None = None
    worker: subprocess.Popen[str] | None = None
    step_count: int = 0
    last_info: dict[str, Any] = field(default_factory=dict)
    last_frame: dict[str, Any] | None = None

    def close(self) -> None:
        if self.env is not None:
            self.env.close()
        if self.worker is not None and self.worker.poll() is None:
            try:
                _worker_request(self, {"command": "close"}, timeout=2)
            except BridgeError:
                pass
            self.worker.terminate()
            try:
                self.worker.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.worker.kill()


SESSIONS: dict[str, SimulationSession] = {}


class BridgeError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class SimulationBridgeHandler(BaseHTTPRequestHandler):
    server_version = "OpenEmbodiedSimOpsBridge/0.1"

    def do_GET(self) -> None:
        self._handle("GET")

    def do_POST(self) -> None:
        self._handle("POST")

    def do_DELETE(self) -> None:
        self._handle("DELETE")

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _handle(self, method: str) -> None:
        try:
            path = urlparse(self.path).path
            if method == "GET" and path == "/health":
                self._send_json({"status": "ok", "sessions": len(SESSIONS)})
                return
            if method == "GET" and path == "/sessions":
                self._send_json({"sessions": _list_sessions()})
                return
            if method == "POST" and path == "/sessions":
                self._send_json(_create_session(self._read_json()))
                return

            parts = [part for part in path.split("/") if part]
            if len(parts) >= 2 and parts[0] == "sessions":
                session_id = parts[1]
                if method == "DELETE" and len(parts) == 2:
                    self._send_json(_close_session(session_id))
                    return
                session = _session(session_id)
                if method == "GET" and len(parts) == 2:
                    self._send_json(_session_status(session))
                    return
                if method == "POST" and len(parts) == 3 and parts[2] == "actions":
                    self._send_json(_step_session(session, self._read_json()))
                    return
                if method == "GET" and len(parts) == 4 and parts[2] == "frames" and parts[3] == "latest":
                    self._send_json(_latest_frame(session))
                    return
                if method == "POST" and len(parts) == 3 and parts[2] == "playback":
                    self._send_json(_create_playback(session, self._read_json()))
                    return

            raise BridgeError(404, "route not found")
        except BridgeError as exc:
            self._send_json({"detail": exc.detail}, status=exc.status_code)
        except Exception as exc:  # pragma: no cover - keeps bridge failures visible to API clients
            self._send_json({"detail": f"{type(exc).__name__}: {exc}"}, status=500)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _create_session(request: dict[str, Any]) -> dict[str, Any]:
    simulator = request.get("simulator", "maniskill")
    if simulator == "motrixsim":
        return _create_motrixsim_session(request)
    if simulator != "maniskill":
        raise BridgeError(400, f"simulation bridge currently supports maniskill and motrixsim only, got {simulator}")

    task = request.get("task", "PickCube-v1")
    if task != "PickCube-v1":
        raise BridgeError(400, f"simulation bridge currently supports PickCube-v1 only, got {task}")

    robot = request.get("robot", "panda")
    if robot != "panda":
        raise BridgeError(400, f"simulation bridge currently supports panda only, got {robot}")

    import gymnasium as gym
    import mani_skill.envs  # noqa: F401 - registers ManiSkill tasks

    width = int(request.get("render_width") or 512)
    height = int(request.get("render_height") or 512)
    env = gym.make(
        task,
        obs_mode="state_dict",
        control_mode="pd_ee_delta_pose",
        robot_uids=robot,
        render_mode="rgb_array",
        sensor_configs={"width": width, "height": height},
    )
    _, info = env.reset(seed=int(request.get("randomization_seed") or 0))
    session_id = "sim-" + uuid.uuid4().hex[:12]
    session = SimulationSession(
        session_id=session_id,
        request=request,
        simulator="maniskill",
        env=env,
        created_at=time.time(),
        last_info=_jsonable(info),
    )
    SESSIONS[session_id] = session
    session.last_frame = _render_frame(session)
    return _session_status(session) | {"frame": session.last_frame}


def _create_motrixsim_session(request: dict[str, Any]) -> dict[str, Any]:
    task = request.get("task", "MotrixSimStep")
    if task != "MotrixSimStep":
        raise BridgeError(400, f"MotrixSim bridge currently supports MotrixSimStep only, got {task}")

    scene = request.get("scene", "motrixsim_body")
    scene_xml = motrixsim_scene_xml(scene)
    if scene_xml is None or not scene_xml.exists():
        raise BridgeError(503, f"MotrixSim scene XML is not available for {scene}")

    python = motrixsim_python_path()
    if python is None or not python.exists() or not os.access(python, os.X_OK):
        raise BridgeError(503, "MotrixSim Python executable is not configured")

    session_id = "motrix-" + uuid.uuid4().hex[:12]
    command = [
        str(python),
        "-m",
        "embodied_simops.integrations.motrixsim",
        "bridge-worker",
        "--scene-id",
        scene,
        "--scene-xml",
        str(scene_xml),
        "--assets-json",
        json.dumps(request.get("assets", [])),
        "--seed",
        str(int(request.get("randomization_seed") or 0)),
        "--render-width",
        str(int(request.get("render_width") or 640)),
        "--render-height",
        str(int(request.get("render_height") or 480)),
    ]
    worker = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=_motrixsim_worker_env(),
        cwd=str(scene_xml.parent),
        bufsize=1,
    )
    session = SimulationSession(
        session_id=session_id,
        request=request,
        simulator="motrixsim",
        worker=worker,
        created_at=time.time(),
    )
    try:
        ready = _read_worker_json(worker, timeout=20)
    except BridgeError:
        session.close()
        raise
    if ready.get("status") != "running":
        session.close()
        raise BridgeError(500, ready.get("detail") or "MotrixSim worker failed to start")
    _sync_worker_payload(session, ready)
    SESSIONS[session_id] = session
    return _session_status(session) | {"frame": session.last_frame}


def _session(session_id: str) -> SimulationSession:
    session = SESSIONS.get(session_id)
    if session is None:
        raise BridgeError(404, "session not found")
    return session


def _list_sessions() -> list[dict[str, Any]]:
    return [_session_status(session) | {"frame": _frame_summary(session.last_frame)} for session in SESSIONS.values()]


def _close_session(session_id: str) -> dict[str, Any]:
    session = _session(session_id)
    session.close()
    SESSIONS.pop(session_id, None)
    return {"session_id": session_id, "status": "closed"}


def _session_status(session: SimulationSession) -> dict[str, Any]:
    return {
        "session_id": session.session_id,
        "id": session.session_id,
        "status": "running",
        "simulator": session.simulator,
        "task": session.request.get("task", "MotrixSimStep" if session.simulator == "motrixsim" else "PickCube-v1"),
        "robot": session.request.get("robot", "motrix_body" if session.simulator == "motrixsim" else "panda"),
        "scene": session.request.get("scene", "motrixsim_body" if session.simulator == "motrixsim" else "maniskill_tabletop"),
        "assets": session.request.get("assets", []),
        "step": session.step_count,
        "created_at": session.created_at,
        "last_info": session.last_info,
    }


def _step_session(session: SimulationSession, request: dict[str, Any]) -> dict[str, Any]:
    if session.simulator == "motrixsim":
        payload = _worker_request(
            session,
            {
                "command": "action",
                "action": str(request.get("action", "stop")),
                "velocity": float(request.get("velocity", 0.25)),
                "steps": 5,
            },
        )
        _sync_worker_payload(session, payload)
        return _session_status(session) | {"frame": session.last_frame}

    assert session.env is not None
    action = _action_vector(session.env, str(request.get("action", "stop")), float(request.get("velocity", 0.25)))
    _, reward, terminated, truncated, info = session.env.step(action)
    session.step_count += 1
    session.last_info = {
        "reward": _jsonable(reward),
        "terminated": _jsonable(terminated),
        "truncated": _jsonable(truncated),
        "info": _jsonable(info),
    }
    session.last_frame = _render_frame(session)
    return _session_status(session) | {"frame": session.last_frame}


def _action_vector(env: Any, action_name: str, velocity: float) -> Any:
    import numpy as np

    low = getattr(env.action_space, "low", None)
    high = getattr(env.action_space, "high", None)
    shape = env.action_space.shape
    action = np.zeros(shape, dtype="float32")
    magnitude = float(max(0.0, min(1.0, velocity)))
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
    if action_name not in mapping:
        raise BridgeError(400, f"unsupported action: {action_name}")
    index, value = mapping[action_name]
    if action.size:
        action[index] = value
    if low is not None and high is not None:
        action = np.clip(action, low, high)
    return action


def _latest_frame(session: SimulationSession) -> dict[str, Any]:
    if session.simulator == "motrixsim":
        payload = _worker_request(session, {"command": "latest_frame"})
        _sync_worker_payload(session, payload)
        return _session_status(session) | {"frame": session.last_frame}
    if session.last_frame is None:
        session.last_frame = _render_frame(session)
    return _session_status(session) | {"frame": session.last_frame}


def _render_frame(session: SimulationSession) -> dict[str, Any]:
    import numpy as np
    from PIL import Image

    assert session.env is not None
    if hasattr(session.env, "render_rgb_array"):
        frame = session.env.render_rgb_array()
    else:
        frame = session.env.render()
    if hasattr(frame, "detach"):
        frame = frame.detach().cpu().numpy()
    elif hasattr(frame, "cpu"):
        frame = frame.cpu().numpy()
    frame = np.asarray(frame)
    if frame.ndim == 4:
        frame = frame[0]
    if frame.dtype != np.uint8:
        if frame.max(initial=0) <= 1.0:
            frame = frame * 255
        frame = np.clip(frame, 0, 255).astype("uint8")
    buffer = io.BytesIO()
    Image.fromarray(frame).save(buffer, format="PNG")
    data = buffer.getvalue()
    digest = hashlib.sha256(data).hexdigest()
    return {
        "media_type": "image/png",
        "encoding": "base64",
        "data_base64": base64.b64encode(data).decode("ascii"),
        "width": int(frame.shape[1]),
        "height": int(frame.shape[0]),
        "sha256": digest,
        "size_bytes": len(data),
        "step": session.step_count,
    }


def _frame_summary(frame: dict[str, Any] | None) -> dict[str, Any] | None:
    if frame is None:
        return None
    return {
        key: frame[key]
        for key in ["media_type", "width", "height", "sha256", "size_bytes", "step", "render_source"]
        if key in frame
    }


def _create_playback(session: SimulationSession, request: dict[str, Any]) -> dict[str, Any]:
    if session.simulator == "motrixsim":
        return {
            "session_id": session.session_id,
            "status": "ready",
            "source_run_id": request.get("source_run_id"),
            "artifact_path": request.get("artifact_path"),
            "speed": request.get("speed", 1.0),
            "loop": request.get("loop", False),
            "note": "interactive MotrixSim session is live; browser viewport renders returned preview_scene frames",
        }
    return {
        "session_id": session.session_id,
        "status": "ready",
        "source_run_id": request.get("source_run_id"),
        "artifact_path": request.get("artifact_path"),
        "speed": request.get("speed", 1.0),
        "loop": request.get("loop", False),
        "note": "interactive ManiSkill session is live; recorded trajectory playback requires a trajectory artifact",
    }


def _motrixsim_worker_env() -> dict[str, str]:
    env = os.environ.copy()
    pythonpath_parts = []
    configured_pythonpath = env.get("SIMOPS_MOTRIXSIM_PYTHONPATH")
    if configured_pythonpath:
        pythonpath_parts.append(configured_pythonpath)
    pythonpath_parts.append(str(Path(__file__).resolve().parents[1]))
    existing_pythonpath = env.get("PYTHONPATH")
    if existing_pythonpath:
        pythonpath_parts.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(item for item in pythonpath_parts if item))
    return env


def _worker_request(session: SimulationSession, payload: dict[str, Any], *, timeout: float = 10) -> dict[str, Any]:
    worker = session.worker
    if worker is None or worker.stdin is None:
        raise BridgeError(500, "MotrixSim worker is not attached")
    if worker.poll() is not None:
        raise BridgeError(500, _worker_exit_detail(worker))
    worker.stdin.write(json.dumps(payload) + "\n")
    worker.stdin.flush()
    return _read_worker_json(worker, timeout=timeout)


def _read_worker_json(worker: subprocess.Popen[str], *, timeout: float) -> dict[str, Any]:
    assert worker.stdout is not None
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if worker.poll() is not None:
            raise BridgeError(500, _worker_exit_detail(worker))
        readable, _, _ = select.select([worker.stdout], [], [], max(0.0, deadline - time.monotonic()))
        if not readable:
            continue
        line = worker.stdout.readline()
        if not line:
            continue
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("status") == "failed":
            raise BridgeError(500, str(payload.get("detail") or "MotrixSim worker failed"))
        return payload
    raise BridgeError(504, "timed out waiting for MotrixSim worker")


def _sync_worker_payload(session: SimulationSession, payload: dict[str, Any]) -> None:
    session.step_count = int(payload.get("step") or session.step_count)
    session.last_info = payload.get("last_info", session.last_info)
    session.last_frame = payload.get("frame", session.last_frame)


def _worker_exit_detail(worker: subprocess.Popen[str]) -> str:
    stderr = ""
    if worker.stderr is not None:
        try:
            stderr = worker.stderr.read()[-2000:]
        except OSError:
            stderr = ""
    return f"MotrixSim worker exited with code {worker.returncode}: {stderr.strip()}"


def _jsonable(value: Any) -> Any:
    if hasattr(value, "detach"):
        return _jsonable(value.detach().cpu().numpy())
    if hasattr(value, "cpu") and hasattr(value, "numpy"):
        return _jsonable(value.cpu().numpy())
    if hasattr(value, "tolist"):
        return value.tolist()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Open Embodied SimOps ManiSkill interactive bridge")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18082)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), SimulationBridgeHandler)
    print(f"SimOps simulation bridge listening on http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    finally:
        for session in list(SESSIONS.values()):
            session.close()


if __name__ == "__main__":
    main()
