from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from embodied_simops.provenance import ArtifactRecord


class SimOpsStore:
    def __init__(self, state_dir: str | Path):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir = self.state_dir / "runs"
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.state_dir / "simops.sqlite3"
        self._init_db()

    def create_run(self, run_id: str, name: str, run_dir: Path) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (id, name, status, run_dir, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (run_id, name, "running", str(run_dir), _now(), _now()),
            )

    def update_run(self, run_id: str, status: str, error: str | None = None) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE runs SET status = ?, error = ?, updated_at = ? WHERE id = ?",
                (status, error, _now(), run_id),
            )

    def record_stage(
        self,
        *,
        run_id: str,
        stage_id: str,
        status: str,
        adapter: str,
        stdout_path: Path | None,
        stderr_path: Path | None,
        returncode: int | None,
        error: str | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO stages (
                    run_id, stage_id, status, adapter, stdout_path, stderr_path,
                    returncode, error, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, stage_id) DO UPDATE SET
                    status = excluded.status,
                    stdout_path = excluded.stdout_path,
                    stderr_path = excluded.stderr_path,
                    returncode = excluded.returncode,
                    error = excluded.error,
                    updated_at = excluded.updated_at
                """,
                (
                    run_id,
                    stage_id,
                    status,
                    adapter,
                    str(stdout_path) if stdout_path else None,
                    str(stderr_path) if stderr_path else None,
                    returncode,
                    error,
                    _now(),
                ),
            )

    def record_artifact(self, record: ArtifactRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO artifacts (
                    run_id, stage_id, name, role, path, relative_path, sha256,
                    size_bytes, record_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.run_id,
                    record.stage_id,
                    record.name,
                    record.role,
                    record.path,
                    record.relative_path,
                    record.sha256,
                    record.size_bytes,
                    json.dumps(record.model_dump(), sort_keys=True),
                    record.created_at,
                ),
            )

    def get_run(self, run_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
            return dict(row) if row else None

    def get_artifacts(self, run_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT record_json FROM artifacts WHERE run_id = ? ORDER BY created_at",
                (run_id,),
            ).fetchall()
        return [json.loads(row["record_json"]) for row in rows]

    def list_runs(self, limit: int = 50) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM runs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_stages(self, run_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM stages WHERE run_id = ? ORDER BY updated_at",
                (run_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_artifacts(self, role: str | None = None, limit: int = 200) -> list[dict]:
        query = "SELECT record_json FROM artifacts"
        params: list[object] = []
        if role:
            query += " WHERE role = ?"
            params.append(role)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [json.loads(row["record_json"]) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    run_dir TEXT NOT NULL,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS stages (
                    run_id TEXT NOT NULL,
                    stage_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    adapter TEXT NOT NULL,
                    stdout_path TEXT,
                    stderr_path TEXT,
                    returncode INTEGER,
                    error TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (run_id, stage_id)
                );

                CREATE TABLE IF NOT EXISTS artifacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    stage_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    path TEXT NOT NULL,
                    relative_path TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    record_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
