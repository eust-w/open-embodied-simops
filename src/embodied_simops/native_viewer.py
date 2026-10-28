from __future__ import annotations

import argparse
import time

from embodied_simops.integrations.motrixsim import motrixsim_scene_xml


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a native MotrixSim viewer for noVNC wrapping.")
    parser.add_argument("--scene-id", default="motrixsim_body")
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--steps-per-frame", type=int, default=1)
    args = parser.parse_args()

    scene_xml = motrixsim_scene_xml(args.scene_id)
    if scene_xml is None or not scene_xml.exists():
        raise SystemExit(f"MotrixSim scene XML is not available for {args.scene_id}")

    import motrixsim as mx
    from motrixsim.render import RenderApp

    model = mx.load_model(str(scene_xml))
    data = mx.SceneData(model)
    render = RenderApp(headless=False)
    render.launch(model)
    interval = 1.0 / max(1.0, args.fps)
    steps = max(1, min(args.steps_per_frame, 60))
    while not _render_is_closed(render):
        started = time.monotonic()
        for _ in range(steps):
            if hasattr(mx, "step"):
                mx.step(model, data)
            else:
                model.step(data)
        render.sync(data)
        elapsed = time.monotonic() - started
        if elapsed < interval:
            time.sleep(interval - elapsed)


def _render_is_closed(render) -> bool:
    value = getattr(render, "is_closed", False)
    return bool(value() if callable(value) else value)


if __name__ == "__main__":
    main()
