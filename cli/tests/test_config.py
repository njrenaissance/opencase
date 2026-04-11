"""Tests for CLI configuration loading and saving."""

from __future__ import annotations

from pathlib import Path

import pytest

from gideon_cli.config import CLIConfig, load_config, save_config


class TestLoadConfig:
    """Config loading precedence: flags > env > file > defaults."""

    def test_defaults(self, tmp_gideon_dir: Path) -> None:
        config = load_config()
        assert config.base_url == "http://localhost:8000"
        assert config.timeout == 30.0

    def test_config_file(self, tmp_gideon_dir: Path) -> None:
        cfg = CLIConfig(base_url="http://custom:9000", timeout=10.0)
        save_config(cfg)

        config = load_config()
        assert config.base_url == "http://custom:9000"
        assert config.timeout == 10.0

    def test_env_overrides_file(
        self, tmp_gideon_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        save_config(CLIConfig(base_url="http://file:1000", timeout=5.0))
        monkeypatch.setenv("GIDEON_BASE_URL", "http://env:2000")
        monkeypatch.setenv("GIDEON_TIMEOUT", "15")

        config = load_config()
        assert config.base_url == "http://env:2000"
        assert config.timeout == 15.0

    def test_flags_override_env(
        self, tmp_gideon_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GIDEON_BASE_URL", "http://env:2000")
        monkeypatch.setenv("GIDEON_TIMEOUT", "15")

        config = load_config(base_url="http://flag:3000", timeout=99.0)
        assert config.base_url == "http://flag:3000"
        assert config.timeout == 99.0

    def test_missing_file_uses_defaults(self, tmp_gideon_dir: Path) -> None:
        config = load_config()
        assert config.base_url == "http://localhost:8000"

    @pytest.mark.parametrize(
        ("flag_url", "env_url", "file_url", "expected"),
        [
            ("http://flag", None, None, "http://flag"),
            (None, "http://env", None, "http://env"),
            (None, None, "http://file", "http://file"),
            (None, None, None, "http://localhost:8000"),
        ],
    )
    def test_precedence_chain(
        self,
        tmp_gideon_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        flag_url: str | None,
        env_url: str | None,
        file_url: str | None,
        expected: str,
    ) -> None:
        if file_url:
            save_config(CLIConfig(base_url=file_url))
        if env_url:
            monkeypatch.setenv("GIDEON_BASE_URL", env_url)

        config = load_config(base_url=flag_url)
        assert config.base_url == expected


class TestSaveConfig:
    def test_round_trip(self, tmp_gideon_dir: Path) -> None:
        original = CLIConfig(base_url="http://test:8080", timeout=42.0)
        save_config(original)
        loaded = load_config()
        assert loaded == original

    def test_creates_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        nested = tmp_path / "new" / ".gideon"
        monkeypatch.setattr("gideon_cli.config.gideon_dir", lambda: nested)
        monkeypatch.setattr(
            "gideon_cli.config.config_path", lambda: nested / "config.toml"
        )

        save_config(CLIConfig())
        assert (nested / "config.toml").exists()
