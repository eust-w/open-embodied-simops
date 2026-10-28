from __future__ import annotations

import sys

from embodied_simops import simulation_bridge


def _write_fake_motrixsim(tmp_path):
    pythonpath = tmp_path / "site"
    package = pythonpath / "motrixsim"
    package.mkdir(parents=True)
    package.joinpath("__init__.py").write_text(
        """
__version__ = "0.0.bridge-test"


class SceneModel:
    num_geoms = 2
    num_dof_pos = 9
    num_dof_vel = 8
    num_actuators = 0
    geom_names = ["floor", "cube"]
    joint_names = [None]
    link_names = ["free_cube"]
    cameras = []


class SceneData:
    def __init__(self, model):
        self.dof_pos = [0.0, 0.0, 1.5, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0]
        self.dof_vel = [0.0] * 8
        self.actuator_ctrls = []

    def set_dof_vel(self, value):
        self.dof_vel = list(value)

    def set_dof_pos(self, value):
        self.dof_pos = list(value)


def load_model(path):
    return SceneModel()


def step(model, data):
    data.dof_pos[0] += data.dof_vel[0] * 0.1
    data.dof_pos[1] += data.dof_vel[1] * 0.1
    data.dof_pos[2] += data.dof_vel[2] * 0.1
""",
        encoding="utf-8",
    )

    docs = tmp_path / "motrixsim-docs"
    xml = docs / "examples" / "assets" / "body.xml"
    xml.parent.mkdir(parents=True)
    xml.write_text(
        """
<mujoco>
  <worldbody>
    <geom name="floor" type="plane" size="5 5 0.1" pos="0 0 0" rgba="0.8 0.9 0.8 1"/>
    <body name="free_cube" pos="0 0 1.5">
      <geom name="cube" type="box" size="0.25 0.25 0.25" pos="0 0 0" rgba="1 0 0 1"/>
    </body>
  </worldbody>
</mujoco>
""",
        encoding="utf-8",
    )
    return pythonpath, docs


def test_motrixsim_bridge_creates_live_preview_session_and_steps(monkeypatch, tmp_path):
    pythonpath, docs = _write_fake_motrixsim(tmp_path)
    monkeypatch.setenv("SIMOPS_MOTRIXSIM_PYTHON", sys.executable)
    monkeypatch.setenv("SIMOPS_MOTRIXSIM_PYTHONPATH", str(pythonpath))
    monkeypatch.setenv("SIMOPS_MOTRIXSIM_DOCS", str(docs))
    monkeypatch.setenv("SIMOPS_MOTRIXSIM_HOME", str(tmp_path / "MotrixLab"))

    created = simulation_bridge._create_session(
        {
            "simulator": "motrixsim",
            "robot": "motrix_body",
            "scene": "motrixsim_body",
            "task": "MotrixSimStep",
            "assets": ["body", "cube"],
            "randomization_seed": 3,
        }
    )
    session = simulation_bridge._session(created["session_id"])
    first_cube = next(item for item in created["frame"]["preview_scene"]["objects"] if item["id"] == "cube")

    stepped = simulation_bridge._step_session(session, {"action": "forward", "velocity": 0.5})
    second_cube = next(item for item in stepped["frame"]["preview_scene"]["objects"] if item["id"] == "cube")
    latest = simulation_bridge._latest_frame(session)
    sessions = simulation_bridge._list_sessions()

    assert created["simulator"] == "motrixsim"
    assert created["frame"]["media_type"] == "application/vnd.simops.preview_scene+json"
    assert stepped["step"] == 1
    assert second_cube["position"][0] > first_cube["position"][0]
    assert latest["frame"]["sha256"] == stepped["frame"]["sha256"]
    assert latest["last_info"]["action"] == "forward"
    assert any(item["session_id"] == created["session_id"] for item in sessions)

    closed = simulation_bridge._close_session(session.session_id)
    assert closed["status"] == "closed"
    assert session.session_id not in simulation_bridge.SESSIONS


def test_motrixsim_bridge_returns_real_rendered_png_when_renderer_is_available(monkeypatch, tmp_path):
    pythonpath, docs = _write_fake_motrixsim(tmp_path)
    package = pythonpath / "motrixsim"
    package.joinpath("__init__.py").write_text(
        package.joinpath("__init__.py").read_text(encoding="utf-8").replace(
            "    cameras = []",
            """
    class Camera:
        def set_render_target(self, name, width, height):
            self.width = width
            self.height = height

    cameras = [Camera()]
""",
        ),
        encoding="utf-8",
    )
    package.joinpath("render.py").write_text(
        """
class Image:
    def __init__(self, was_synced):
        self.pixels = None
        if was_synced:
            self.pixels = [
                [[120, 80, 40], [121, 80, 40], [120, 81, 40], [120, 80, 41]],
                [[120, 80, 40], [121, 80, 40], [120, 81, 40], [120, 80, 41]],
                [[120, 80, 40], [121, 80, 40], [120, 81, 40], [120, 80, 41]],
            ]


class CaptureTask:
    def __init__(self, was_synced):
        self.was_synced = was_synced
        self.state = "used"

    def take_image(self):
        return Image(self.was_synced)


class RenderCamera:
    def __init__(self, app):
        self.app = app

    def capture(self):
        return CaptureTask(self.app.sync_count > 0)


class RenderApp:
    def __init__(self, headless=True):
        self.headless = headless
        self.sync_count = 0

    def launch(self, model):
        self.model = model

    def get_camera(self, index):
        return RenderCamera(self)

    def sync(self, data):
        self.sync_count += 1
        self.data = data
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("SIMOPS_MOTRIXSIM_PYTHON", sys.executable)
    monkeypatch.setenv("SIMOPS_MOTRIXSIM_PYTHONPATH", str(pythonpath))
    monkeypatch.setenv("SIMOPS_MOTRIXSIM_DOCS", str(docs))
    monkeypatch.setenv("SIMOPS_MOTRIXSIM_HOME", str(tmp_path / "MotrixLab"))

    created = simulation_bridge._create_session(
        {
            "simulator": "motrixsim",
            "robot": "motrix_body",
            "scene": "motrixsim_body",
            "task": "MotrixSimStep",
            "assets": ["body", "cube"],
            "randomization_seed": 3,
        }
    )
    session = simulation_bridge._session(created["session_id"])
    stepped = simulation_bridge._step_session(session, {"action": "forward", "velocity": 0.5})

    assert stepped["frame"]["media_type"] == "image/png"
    assert stepped["frame"]["encoding"] == "base64"
    assert stepped["frame"]["data_base64"]
    assert stepped["frame"]["preview_scene"]["schema_version"] == "simops.preview_scene/v1"
    assert stepped["frame"]["render_source"] == "motrixsim.headless"

    session.close()
    simulation_bridge.SESSIONS.pop(session.session_id, None)
