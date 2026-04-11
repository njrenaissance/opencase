"""Tests for client-side file hashing utility."""

from __future__ import annotations

import hashlib

from gideon.hashing import hash_file


def test_hash_file(tmp_path) -> None:
    """hash_file returns correct SHA-256 hex digest."""
    content = b"hello world"
    f = tmp_path / "test.txt"
    f.write_bytes(content)

    result = hash_file(f)
    expected = hashlib.sha256(content).hexdigest()
    assert result == expected


def test_hash_file_large(tmp_path) -> None:
    """hash_file handles files larger than the chunk size."""
    # Create a file larger than the 64 KB chunk size
    content = b"x" * (128 * 1024)
    f = tmp_path / "large.bin"
    f.write_bytes(content)

    result = hash_file(f)
    expected = hashlib.sha256(content).hexdigest()
    assert result == expected
