"""CLI configuration — load/save settings from flags, env, and config file."""

from __future__ import annotations

import os
import stat
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

import tomli_w

_DEFAULT_BASE_URL = "http://localhost:8000"
_DEFAULT_TIMEOUT = 30.0


def gideon_dir() -> Path:
    """Return ``~/.gideon/``, the CLI data directory."""
    return Path.home() / ".gideon"


def config_path() -> Path:
    """Return the path to the CLI config file."""
    return gideon_dir() / "config.toml"


@dataclass(frozen=True)
class CLIConfig:
    """Resolved CLI configuration."""

    base_url: str = _DEFAULT_BASE_URL
    timeout: float = _DEFAULT_TIMEOUT


def load_config(
    *,
    base_url: str | None = None,
    timeout: float | None = None,
) -> CLIConfig:
    """Merge config from flags > env vars > config file > defaults.

    Parameters that are ``None`` fall through to the next source.
    """
    # Layer 3: config file (lowest precedence)
    file_base_url: str | None = None
    file_timeout: float | None = None

    path = config_path()
    if path.exists():
        with path.open("rb") as f:
            data = tomllib.load(f)
        file_base_url = data.get("base_url")
        raw_timeout = data.get("timeout")
        if raw_timeout is not None:
            file_timeout = float(raw_timeout)

    # Layer 2: env vars
    env_base_url = os.environ.get("GIDEON_BASE_URL")
    env_timeout_raw = os.environ.get("GIDEON_TIMEOUT")
    env_timeout = float(env_timeout_raw) if env_timeout_raw else None

    # Merge: flags > env > file > defaults (use is not None, not truthiness)
    resolved_url = (
        base_url
        if base_url is not None
        else env_base_url
        if env_base_url is not None
        else file_base_url
        if file_base_url is not None
        else _DEFAULT_BASE_URL
    )
    resolved_timeout = (
        timeout
        if timeout is not None
        else env_timeout
        if env_timeout is not None
        else file_timeout
        if file_timeout is not None
        else _DEFAULT_TIMEOUT
    )

    return CLIConfig(base_url=resolved_url, timeout=resolved_timeout)


def save_config(config: CLIConfig) -> None:
    """Write configuration to ``~/.gideon/config.toml``."""
    directory = gideon_dir()
    directory.mkdir(parents=True, exist_ok=True)
    if sys.platform != "win32":
        directory.chmod(stat.S_IRWXU)

    path = config_path()
    data: dict[str, object] = {
        "base_url": config.base_url,
        "timeout": config.timeout,
    }
    path.write_bytes(tomli_w.dumps(data).encode())
