from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.10.
    import tomli as tomllib


class ConfigError(ValueError):
    """Raised when a task configuration is invalid."""


REQUIRED_STACK_KEYS = (
    "simulator",
    "robot",
    "scene",
    "assets",
    "task",
    "sensors",
    "randomization",
    "data_format",
    "training_strategy",
    "deployment_targets",
)


class RuntimeConfig(BaseModel):
    max_parallel_jobs: int = Field(default=1, ge=1)


class SourceRef(BaseModel):
    uri: str = Field(min_length=1)
    version: str = Field(min_length=1)
    license: str = Field(min_length=1)
    digest: str | None = None
    commit: str | None = None


class ComponentRef(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str | None = None
    kind: str = Field(min_length=1)
    source: SourceRef


class OutputSpec(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = Field(min_length=1)
    path: str = Field(min_length=1)
    role: str = Field(min_length=1)
    media_type: str | None = None

    @field_validator("path")
    @classmethod
    def path_must_be_relative(cls, value: str) -> str:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("artifact output paths must stay inside the run directory")
        return value


class StageConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(min_length=1)
    adapter: str = Field(min_length=1)
    uses: list[str] = Field(default_factory=list)
    outputs: list[OutputSpec] = Field(default_factory=list)
    command: list[str] | None = None
    cwd: str | None = None
    env: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: int | None = Field(default=None, gt=0)
    executables: list[str] = Field(default_factory=list)
    python_modules: list[str] = Field(default_factory=list)
    env_vars: list[str] = Field(default_factory=list)
    policy_artifact: str | None = None
    policy_path: str | None = None
    output_dir: str | None = None
    ros2: dict[str, Any] = Field(default_factory=dict)
    lerobot: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_adapter_contract(self) -> "StageConfig":
        if self.adapter == "command" and not self.command:
            raise ValueError("command adapter requires a non-empty command")
        if self.adapter == "deployment_export":
            if not (self.policy_artifact or self.policy_path):
                raise ValueError("deployment_export requires policy_artifact or policy_path")
            if not self.output_dir:
                raise ValueError("deployment_export requires output_dir")
        return self


class TaskConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: str
    name: str = Field(min_length=1)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    components: dict[str, ComponentRef]
    pipeline: list[StageConfig]
    stack: dict[str, Any]

    @model_validator(mode="after")
    def validate_closed_loop(self) -> "TaskConfig":
        if self.schema_version != "simops/v1":
            raise ValueError("schema_version must be simops/v1")

        missing_stack_keys = [key for key in REQUIRED_STACK_KEYS if key not in self.stack]
        if missing_stack_keys:
            joined = ", ".join(f"stack.{key}" for key in missing_stack_keys)
            raise ValueError(f"missing required closed-loop dimensions: {joined}")

        component_ids = set(self.components)
        for component_id, component in self.components.items():
            component.id = component_id

        for stage in self.pipeline:
            for component_id in stage.uses:
                if component_id not in component_ids:
                    raise ValueError(f"pipeline.{stage.id}.uses references unknown component {component_id}")

        output_names: set[str] = set()
        for stage in self.pipeline:
            for output in stage.outputs:
                if output.name in output_names:
                    raise ValueError(f"artifact output name {output.name} is duplicated")
                output_names.add(output.name)
        return self


def load_task_config(path: str | Path) -> TaskConfig:
    config_path = Path(path)
    try:
        raw = _load_mapping(config_path)
        return TaskConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(_format_validation_error(exc)) from exc
    except (OSError, yaml.YAMLError, json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"failed to read {config_path}: {exc}") from exc


def _load_mapping(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")
    if suffix in {".yaml", ".yml"}:
        data = yaml.safe_load(text)
    elif suffix == ".json":
        data = json.loads(text)
    elif suffix == ".toml":
        data = tomllib.loads(text)
    else:
        raise ConfigError(f"unsupported config format: {path.suffix}")

    if not isinstance(data, dict):
        raise ConfigError("task config root must be a mapping")
    return data


def _format_validation_error(exc: ValidationError) -> str:
    parts: list[str] = []
    for error in exc.errors():
        loc = ".".join(str(item) for item in error["loc"])
        parts.append(f"{loc}: {error['msg']}")
    return "; ".join(parts)
