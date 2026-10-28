from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap Open Embodied SimOps runtime dependencies")
    subparsers = parser.add_subparsers(dest="command", required=True)

    bridge = subparsers.add_parser("install-bridge-service")
    bridge.add_argument("--project-dir", default=os.environ.get("SIMOPS_PROJECT_DIR", "/opt/open-embodied-simops"))
    bridge.add_argument("--python", default=os.environ.get("SIMOPS_MANISKILL_MP_PYTHON", ""))
    bridge.add_argument("--host", default="127.0.0.1")
    bridge.add_argument("--port", type=int, default=18082)

    native_ui = subparsers.add_parser("install-native-ui-service")
    native_ui.add_argument("--project-dir", default=os.environ.get("SIMOPS_PROJECT_DIR", "/opt/open-embodied-simops"))
    native_ui.add_argument("--python", default=os.environ.get("SIMOPS_MOTRIXSIM_PYTHON", "/opt/Motphys/MotrixLab/.venv/bin/python"))
    native_ui.add_argument("--host", default="127.0.0.1")
    native_ui.add_argument("--port", type=int, default=6080)
    native_ui.add_argument("--display", default=":92")

    install = subparsers.add_parser("install-component")
    install.add_argument("component", choices=["maniskill", "lerobot"])
    install.add_argument("--project-dir", default=os.environ.get("SIMOPS_PROJECT_DIR", "/opt/open-embodied-simops"))

    args = parser.parse_args()
    if args.command == "install-bridge-service":
        install_bridge_service(args.project_dir, args.python, args.host, args.port)
    elif args.command == "install-native-ui-service":
        install_native_ui_service(args.project_dir, args.python, args.host, args.port, args.display)
    elif args.command == "install-component":
        install_component(args.component, args.project_dir)


def install_bridge_service(project_dir: str, python_path: str, host: str, port: int) -> None:
    project = Path(project_dir).resolve()
    bridge_python = Path(python_path) if python_path else project / ".maniskill-mp-venv" / "bin" / "python"
    if not bridge_python.exists():
        raise SystemExit(f"ManiSkill Python not found: {bridge_python}")
    unit = f"""[Unit]
Description=Open Embodied SimOps ManiSkill interactive simulation bridge
After=network.target

[Service]
Type=simple
WorkingDirectory={project}
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONPATH={project / "src"}
Environment=SIMOPS_STATE_DIR=/var/lib/open-embodied-simops
ExecStart={bridge_python} -m embodied_simops.simulation_bridge --host {host} --port {port}
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
"""
    unit_path = Path("/etc/systemd/system/simops-bridge.service")
    unit_path.write_text(unit, encoding="utf-8")
    _run(["systemctl", "daemon-reload"])
    _run(["systemctl", "enable", "--now", "simops-bridge.service"])
    _run(["systemctl", "restart", "simops-bridge.service"])
    print(f"installed simops-bridge.service on http://{host}:{port}")


def install_native_ui_service(project_dir: str, python_path: str, host: str, port: int, display: str) -> None:
    project = Path(project_dir).resolve()
    motrix_python = Path(python_path).expanduser()
    if not motrix_python.is_absolute():
        motrix_python = (Path.cwd() / motrix_python).absolute()
    if not motrix_python.exists():
        raise SystemExit(f"MotrixSim Python not found: {motrix_python}")
    _ensure_native_ui_packages()
    novnc_web = _novnc_web_path()
    url = f"http://{host}:{port}/vnc.html?autoconnect=1&resize=scale"
    unit = f"""[Unit]
Description=Open Embodied SimOps native simulator UI via noVNC
After=network.target

[Service]
Type=simple
WorkingDirectory={project}
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONPATH={project / "src"}
Environment=SIMOPS_STATE_DIR=/var/lib/open-embodied-simops
ExecStart=/bin/bash -lc 'set -e; export DISPLAY={display}; Xvfb {display} -screen 0 1280x720x24 -ac +extension GLX +render -noreset & xvfb_pid=$!; sleep 1; x11vnc -display {display} -localhost -nopw -forever -shared -rfbport 5900 -quiet & vnc_pid=$!; {motrix_python} -m embodied_simops.native_viewer --scene-id motrixsim_body --fps 8 & viewer_pid=$!; trap "kill $viewer_pid $vnc_pid $xvfb_pid 2>/dev/null || true" TERM INT EXIT; exec websockify --web={novnc_web} {host}:{port} 127.0.0.1:5900'
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
"""
    Path("/etc/systemd/system/simops-native-ui.service").write_text(unit, encoding="utf-8")
    dropin = Path("/etc/systemd/system/simops-api.service.d")
    dropin.mkdir(parents=True, exist_ok=True)
    (dropin / "native-ui.conf").write_text(f"[Service]\nEnvironment=SIMOPS_NATIVE_SIM_UI_URL={url}\n", encoding="utf-8")
    _run(["systemctl", "daemon-reload"])
    _run(["systemctl", "enable", "--now", "simops-native-ui.service"])
    _run(["systemctl", "restart", "simops-native-ui.service"])
    _run(["systemctl", "restart", "simops-api.service"])
    print(f"installed simops-native-ui.service on {url}")


def install_component(component: str, project_dir: str) -> None:
    project = Path(project_dir).resolve()
    if component == "maniskill":
        python_path = project / ".maniskill-mp-venv" / "bin" / "python"
        if not python_path.exists():
            _run([sys.executable, "-m", "venv", str(project / ".maniskill-mp-venv")])
        _run([str(python_path), "-m", "pip", "install", "--upgrade", "pip"])
        _run([str(python_path), "-m", "pip", "install", "mani_skill==3.0.1"])
        print(f"installed ManiSkill runtime at {python_path}")
        return
    if component == "lerobot":
        python_path = project / ".venv" / "bin" / "python"
        if not python_path.exists():
            _run([sys.executable, "-m", "venv", str(project / ".venv")])
        _run([str(python_path), "-m", "pip", "install", "--upgrade", "pip"])
        _run([str(python_path), "-m", "pip", "install", "-e", f"{project}[dev]", "lerobot==0.4.4"])
        print(f"installed LeRobot runtime at {python_path}")
        return
    raise SystemExit(f"unsupported component: {component}")


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def _ensure_native_ui_packages() -> None:
    missing = [command for command in ["Xvfb", "x11vnc", "websockify"] if not shutil.which(command)]
    if not missing and _novnc_web_path().exists():
        return
    if shutil.which("apt-get"):
        _run(["apt-get", "update"])
        _run(["apt-get", "install", "-y", "xvfb", "x11vnc", "websockify", "novnc"])
        return
    raise SystemExit(f"native UI packages are missing and no supported installer was found: {', '.join(missing)}")


def _novnc_web_path() -> Path:
    for candidate in [Path("/usr/share/novnc"), Path("/usr/share/novnc/web"), Path("/usr/share/webapps/novnc")]:
        if (candidate / "vnc.html").exists():
            return candidate
    return Path("/usr/share/novnc")


if __name__ == "__main__":
    main()
