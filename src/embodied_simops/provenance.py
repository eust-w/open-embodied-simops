from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from embodied_simops.config import ComponentRef, OutputSpec


class ArtifactRecord(BaseModel):
    run_id: str
    stage_id: str
    name: str
    role: str
    path: str
    relative_path: str
    sha256: str
    size_bytes: int
    created_at: str
    media_type: str | None = None
    source_components: list[ComponentRef]


def record_artifact(
    *,
    run_id: str,
    stage_id: str,
    run_dir: Path,
    output: OutputSpec,
    source_components: list[ComponentRef],
) -> ArtifactRecord:
    artifact_path = run_dir / output.path
    digest, size_bytes = sha256_path(artifact_path)
    return ArtifactRecord(
        run_id=run_id,
        stage_id=stage_id,
        name=output.name,
        role=output.role,
        path=str(artifact_path),
        relative_path=output.path,
        sha256=digest,
        size_bytes=size_bytes,
        created_at=datetime.now(timezone.utc).isoformat(),
        media_type=output.media_type,
        source_components=source_components,
    )


def append_ledger(run_dir: Path, record: ArtifactRecord) -> None:
    ledger_dir = run_dir / "provenance"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = ledger_dir / "artifacts.jsonl"
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record.model_dump(), sort_keys=True) + "\n")


def sha256_path(path: Path) -> tuple[str, int]:
    if path.is_file():
        return _sha256_file(path), path.stat().st_size
    if path.is_dir():
        digest = hashlib.sha256()
        total_size = 0
        for child in sorted(item for item in path.rglob("*") if item.is_file()):
            relative = child.relative_to(path).as_posix()
            file_hash = _sha256_file(child)
            total_size += child.stat().st_size
            digest.update(relative.encode("utf-8"))
            digest.update(b"\0")
            digest.update(file_hash.encode("ascii"))
            digest.update(b"\0")
        return digest.hexdigest(), total_size
    raise FileNotFoundError(path)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
