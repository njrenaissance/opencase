"""Client-side SHA-256 hashing for local files."""

from __future__ import annotations

import hashlib
from pathlib import Path

_CHUNK_SIZE = 64 * 1024  # 64 KB


def hash_file(path: Path) -> str:
    """Compute the SHA-256 hex digest of a file, reading in 64 KB chunks."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(_CHUNK_SIZE):
            hasher.update(chunk)
    return hasher.hexdigest()
