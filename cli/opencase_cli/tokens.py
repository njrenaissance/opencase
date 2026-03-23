"""Token persistence — store/load JWT tokens to ``~/.opencase/tokens.json``."""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

from opencase_cli.config import opencase_dir


def _tokens_path() -> Path:
    """Return the path to the stored tokens file."""
    return opencase_dir() / "tokens.json"


def save_tokens(access_token: str, refresh_token: str) -> None:
    """Persist tokens to disk with restricted permissions.

    On Unix, the file is created atomically with 0600 permissions
    to avoid a window where tokens are world-readable.
    """
    path = _tokens_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    content = json.dumps(
        {"access_token": access_token, "refresh_token": refresh_token}
    ).encode()

    if sys.platform != "win32":
        fd = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
            stat.S_IRUSR | stat.S_IWUSR,
        )
        try:
            os.write(fd, content)
        finally:
            os.close(fd)
    else:
        path.write_bytes(content)


def load_tokens() -> tuple[str, str] | None:
    """Load stored tokens. Returns ``(access, refresh)`` or ``None``."""
    path = _tokens_path()
    if not path.exists():
        return None

    data = json.loads(path.read_text(encoding="utf-8"))
    access = data.get("access_token")
    refresh = data.get("refresh_token")
    if access and refresh:
        return (access, refresh)
    return None


def clear_tokens() -> None:
    """Delete the stored tokens file."""
    path = _tokens_path()
    if path.exists():
        path.unlink()
