"""Unit tests for application configuration layered loading.

monkeypatch is used throughout to auto-revert environment variables and
working directory changes after each test, preventing state leakage
between tests (e.g. OPENCASE_* env vars or chdir to fixtures/).
"""

import os
from importlib.metadata import version
from pathlib import Path

import pytest

from app.core.config import Settings

DEFAULTS = {
    "app_name": "OpenCase",
    "app_version": version("opencase"),
    "debug": False,
    "deployment_mode": "airgapped",
}

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Remove any OPENCASE_ env vars so each test starts clean."""
    for key in list(os.environ):
        if key.startswith("OPENCASE_"):
            monkeypatch.delenv(key, raising=False)


def test_defaults():
    cfg = Settings()
    assert cfg.model_dump() == DEFAULTS


def test_env_vars_override_defaults(monkeypatch):
    monkeypatch.setenv("OPENCASE_APP_NAME", "TestCase")
    monkeypatch.setenv("OPENCASE_DEBUG", "true")
    cfg = Settings()
    assert cfg.model_dump() == {**DEFAULTS, "app_name": "TestCase", "debug": True}


def test_json_config_overrides_defaults(monkeypatch):
    monkeypatch.chdir(FIXTURES_DIR)
    cfg = Settings()
    assert cfg.model_dump() == {
        **DEFAULTS,
        "app_name": "JSONCase",
        "deployment_mode": "internet-accessible",
    }


def test_env_vars_override_json(monkeypatch):
    monkeypatch.chdir(FIXTURES_DIR)
    monkeypatch.setenv("OPENCASE_APP_NAME", "EnvCase")
    cfg = Settings()
    assert cfg.model_dump() == {
        **DEFAULTS,
        "app_name": "EnvCase",
        "deployment_mode": "internet-accessible",
    }


def test_dotenv_overrides_json(monkeypatch):
    monkeypatch.chdir(FIXTURES_DIR)
    cfg = Settings(_env_file=FIXTURES_DIR / "test.env")
    assert cfg.model_dump() == {
        **DEFAULTS,
        "app_name": "DotenvCase",
        "deployment_mode": "internet-accessible",
    }


def test_bool_casting_from_env(monkeypatch):
    monkeypatch.setenv("OPENCASE_DEBUG", "false")
    cfg = Settings()
    assert cfg.model_dump() == DEFAULTS


def test_missing_json_is_ignored(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = Settings()
    assert cfg.model_dump() == DEFAULTS
