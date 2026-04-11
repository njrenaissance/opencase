"""Tests for token persistence."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from gideon_cli.tokens import clear_tokens, load_tokens, save_tokens


class TestTokens:
    def test_round_trip(self, tmp_gideon_dir: Path) -> None:
        save_tokens("access-123", "refresh-456")
        result = load_tokens()
        assert result == ("access-123", "refresh-456")

    def test_load_missing_returns_none(self, tmp_gideon_dir: Path) -> None:
        assert load_tokens() is None

    def test_clear_removes_file(self, tmp_gideon_dir: Path) -> None:
        save_tokens("a", "r")
        clear_tokens()
        assert load_tokens() is None

    def test_clear_missing_is_noop(self, tmp_gideon_dir: Path) -> None:
        clear_tokens()  # should not raise

    @pytest.mark.skipif(
        sys.platform == "win32", reason="chmod not supported on Windows"
    )
    def test_file_permissions(self, tmp_gideon_dir: Path) -> None:
        save_tokens("a", "r")
        token_path = tmp_gideon_dir / "tokens.json"
        mode = token_path.stat().st_mode & 0o777
        assert mode == 0o600

    def test_load_empty_tokens_returns_none(self, tmp_gideon_dir: Path) -> None:
        token_path = tmp_gideon_dir / "tokens.json"
        token_path.write_text('{"access_token": "", "refresh_token": ""}')
        assert load_tokens() is None
