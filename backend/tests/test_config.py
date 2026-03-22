"""Unit tests for application configuration layered loading.

monkeypatch is used throughout to auto-revert environment variables and
working directory changes after each test, preventing state leakage
between tests (e.g. OPENCASE_* env vars or chdir to fixtures/).
"""

import os
from importlib.metadata import version
from pathlib import Path

import pytest
from dotenv import dotenv_values
from pydantic import ValidationError

from app.core.config import ApiSettings, AuthSettings, DbSettings, Settings

# Read required test values from .env.test — single source of truth.
_ENV_TEST = dotenv_values(Path(__file__).parent.parent / ".env.test")

DEFAULTS = {
    "app_name": "OpenCase",
    "app_version": version("opencase"),
    "debug": False,
    "log_level": "INFO",
    "log_output": "stdout",
    "deployment_mode": "airgapped",
    "api": {
        "host": "0.0.0.0",
        "port": 8000,
    },
    "otel": {
        "enabled": False,
        "exporter": "console",
        "endpoint": "http://localhost:4318",
        "service_name": "opencase-api",
        "sample_rate": 1.0,
    },
    "auth": {
        "secret_key": _ENV_TEST["OPENCASE_AUTH_SECRET_KEY"],
        "algorithm": "HS256",
        "access_token_expire_minutes": 15,
        "refresh_token_expire_days": 7,
        "totp_issuer": "OpenCase",
        "totp_digest": "sha1",
        "totp_window": 1,
        "bcrypt_rounds": 4,
        "login_lockout_attempts": 5,
        "login_lockout_minutes": 15,
    },
    "db": {
        "url": _ENV_TEST["OPENCASE_DB_URL"],
        "pool_size": 10,
        "max_overflow": 20,
        "pool_pre_ping": True,
        "echo": False,
    },
    "admin": {
        "email": _ENV_TEST.get("OPENCASE_ADMIN_EMAIL"),
        "password": _ENV_TEST.get("OPENCASE_ADMIN_PASSWORD"),
        "first_name": _ENV_TEST.get("OPENCASE_ADMIN_FIRST_NAME", "Admin"),
        "last_name": _ENV_TEST.get("OPENCASE_ADMIN_LAST_NAME", "User"),
        "firm_name": _ENV_TEST.get("OPENCASE_ADMIN_FIRM_NAME", "Default Firm"),
    },
}

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Remove any OPENCASE_ env vars so each test starts clean,
    then reload required fields from .env.test."""
    for key in list(os.environ):
        if key.startswith("OPENCASE_"):
            monkeypatch.delenv(key, raising=False)
    for key, value in _ENV_TEST.items():
        if value is not None:
            monkeypatch.setenv(key, value)


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


# ---------------------------------------------------------------------------
# ApiSettings — tested directly
# ---------------------------------------------------------------------------


def test_api_defaults():
    cfg = ApiSettings()
    assert cfg.host == "0.0.0.0"
    assert cfg.port == 8000


def test_api_env_override(monkeypatch):
    monkeypatch.setenv("OPENCASE_API_PORT", "9000")
    cfg = ApiSettings()
    assert cfg.port == 9000


# ---------------------------------------------------------------------------
# AuthSettings — tested directly so monkeypatch applies to its own env reads
# ---------------------------------------------------------------------------


def test_auth_missing_secret_key_raises(monkeypatch):
    monkeypatch.delenv("OPENCASE_AUTH_SECRET_KEY", raising=False)
    with pytest.raises(ValidationError):
        AuthSettings()


def test_auth_defaults(monkeypatch):
    cfg = AuthSettings()
    assert cfg.algorithm == "HS256"
    assert cfg.access_token_expire_minutes == 15
    assert cfg.refresh_token_expire_days == 7
    assert cfg.totp_issuer == "OpenCase"
    assert cfg.totp_window == 1
    assert cfg.totp_digest == "sha1"
    assert cfg.bcrypt_rounds == 4
    assert cfg.login_lockout_attempts == 5
    assert cfg.login_lockout_minutes == 15


def test_auth_env_override(monkeypatch):
    monkeypatch.setenv("OPENCASE_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    cfg = AuthSettings()
    assert cfg.access_token_expire_minutes == 30


def test_auth_prefix_isolation(monkeypatch):
    # OPENCASE_SECRET_KEY (wrong prefix) must not satisfy OPENCASE_AUTH_SECRET_KEY
    monkeypatch.setenv("OPENCASE_SECRET_KEY", "wrong")
    monkeypatch.delenv("OPENCASE_AUTH_SECRET_KEY", raising=False)
    with pytest.raises(ValidationError):
        AuthSettings()


# ---------------------------------------------------------------------------
# DbSettings — tested directly so monkeypatch applies to its own env reads
# ---------------------------------------------------------------------------


def test_db_missing_url_raises(monkeypatch):
    monkeypatch.delenv("OPENCASE_DB_URL", raising=False)
    with pytest.raises(ValidationError):
        DbSettings()


def test_db_defaults(monkeypatch):
    cfg = DbSettings()
    assert cfg.pool_size == 10
    assert cfg.max_overflow == 20
    assert cfg.pool_pre_ping is True
    assert cfg.echo is False


def test_db_env_override(monkeypatch):
    monkeypatch.setenv("OPENCASE_DB_POOL_SIZE", "20")
    cfg = DbSettings()
    assert cfg.pool_size == 20


def test_db_prefix_isolation(monkeypatch):
    # OPENCASE_URL (wrong prefix) must not satisfy OPENCASE_DB_URL
    monkeypatch.setenv("OPENCASE_URL", "wrong")
    monkeypatch.delenv("OPENCASE_DB_URL", raising=False)
    with pytest.raises(ValidationError):
        DbSettings()
