"""Validated runtime configuration and workspace path containment."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


class ConfigurationError(RuntimeError):
    """Raised when runtime configuration is unsafe or incomplete."""


@dataclass(frozen=True)
class Settings:
    workspace: Path
    backend: Literal["mock", "zosapi"] = "mock"
    opticstudio_dir: Path | None = None
    nethelper_dll: Path | None = None
    connect_mode: Literal["extension", "standalone"] = "extension"
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Settings":
        raw_workspace = os.getenv("ZEMAX_WORKSPACE")
        if not raw_workspace:
            raise ConfigurationError("ZEMAX_WORKSPACE must point to an existing writable directory")
        workspace = Path(raw_workspace).expanduser().resolve()
        if not workspace.is_dir():
            raise ConfigurationError(f"ZEMAX_WORKSPACE is not an existing directory: {workspace}")
        if not os.access(workspace, os.W_OK):
            raise ConfigurationError(f"ZEMAX_WORKSPACE is not writable: {workspace}")

        backend = os.getenv("ZEMAX_BACKEND", "mock").lower()
        if backend not in {"mock", "zosapi"}:
            raise ConfigurationError("ZEMAX_BACKEND must be 'mock' or 'zosapi'")
        connect_mode = os.getenv("ZEMAX_CONNECT_MODE", "extension").lower()
        if connect_mode not in {"extension", "standalone"}:
            raise ConfigurationError("ZEMAX_CONNECT_MODE must be 'extension' or 'standalone'")
        level = os.getenv("ZEMAX_LOG_LEVEL", "INFO").upper()
        if level not in logging.getLevelNamesMapping():
            raise ConfigurationError(f"Invalid ZEMAX_LOG_LEVEL: {level}")

        def optional_path(name: str) -> Path | None:
            value = os.getenv(name)
            return Path(value).expanduser().resolve() if value else None

        return cls(
            workspace=workspace,
            backend=backend,  # type: ignore[arg-type]
            opticstudio_dir=optional_path("ZEMAX_OPTICSTUDIO_DIR"),
            nethelper_dll=optional_path("ZEMAX_ZOSAPI_NETHELPER_DLL"),
            connect_mode=connect_mode,  # type: ignore[arg-type]
            log_level=level,
        )

    def resolve_workspace_path(self, relative_path: str, *, suffix: str | None = None) -> Path:
        candidate_input = Path(relative_path)
        if candidate_input.is_absolute():
            raise ValueError("Path must be relative to ZEMAX_WORKSPACE")
        candidate = (self.workspace / candidate_input).resolve()
        try:
            candidate.relative_to(self.workspace)
        except ValueError as exc:
            raise ValueError("Path traversal outside ZEMAX_WORKSPACE is forbidden") from exc
        if suffix and candidate.suffix.lower() != suffix.lower():
            raise ValueError(f"Only {suffix} files are allowed")
        return candidate
