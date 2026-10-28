from __future__ import annotations

import json
from pathlib import Path

import typer

from embodied_simops.config import ConfigError, load_task_config
from embodied_simops.orchestrator import PipelineError, SimOpsEngine
from embodied_simops.storage import SimOpsStore

app = typer.Typer(help="Private embodied SimOps orchestration.")


@app.command()
def validate(config: Path) -> None:
    """Validate a SimOps task configuration."""
    try:
        task = load_task_config(config)
    except ConfigError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"valid: {task.name}")


@app.command()
def run(config: Path, state_dir: Path = typer.Option(Path(".simops"), "--state-dir")) -> None:
    """Run a configured SimOps pipeline serially."""
    try:
        task = load_task_config(config)
        result = SimOpsEngine(state_dir).run(task)
    except (ConfigError, PipelineError) as exc:
        raise typer.Exit(code=_print_error(exc)) from exc
    typer.echo(json.dumps({"run_id": result.run_id, "status": result.status, "run_dir": str(result.run_dir)}, indent=2))


@app.command()
def status(run_id: str, state_dir: Path = typer.Option(Path(".simops"), "--state-dir")) -> None:
    """Show a run status from local SQLite state."""
    store = SimOpsStore(state_dir)
    record = store.get_run(run_id)
    if record is None:
        raise typer.BadParameter(f"unknown run_id: {run_id}")
    typer.echo(json.dumps(record, indent=2, sort_keys=True))


@app.command()
def artifacts(run_id: str, state_dir: Path = typer.Option(Path(".simops"), "--state-dir")) -> None:
    """List artifact provenance records for a run."""
    store = SimOpsStore(state_dir)
    typer.echo(json.dumps(store.get_artifacts(run_id), indent=2, sort_keys=True))


def _print_error(exc: Exception) -> int:
    typer.echo(f"error: {exc}", err=True)
    return 1


if __name__ == "__main__":
    app()
