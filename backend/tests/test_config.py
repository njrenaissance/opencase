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

from app.core.config import (
    ApiSettings,
    AuthSettings,
    CelerySettings,
    DbSettings,
    FlowerSettings,
    RedisSettings,
    S3Settings,
    Settings,
    redact_settings,
)

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
    "redis": {
        "host": _ENV_TEST.get("OPENCASE_REDIS_HOST", "redis"),
        "port": int(_ENV_TEST.get("OPENCASE_REDIS_PORT", "6379")),
        "db": int(_ENV_TEST.get("OPENCASE_REDIS_DB", "0")),
        "password": None,
        "ssl": False,
        "pool_size": int(_ENV_TEST.get("OPENCASE_REDIS_POOL_SIZE", "10")),
        "url": f"redis://{_ENV_TEST.get('OPENCASE_REDIS_HOST', 'redis')}:6379/0",
    },
    "celery": {
        # broker_url is not in .env.test — derived from RedisSettings
        # by the Settings model validator.
        "broker_url": (
            f"redis://{_ENV_TEST.get('OPENCASE_REDIS_HOST', 'redis')}"
            f":{_ENV_TEST.get('OPENCASE_REDIS_PORT', '6379')}"
            f"/{_ENV_TEST.get('OPENCASE_REDIS_DB', '0')}"
        ),
        "result_backend": _ENV_TEST.get("OPENCASE_CELERY_RESULT_BACKEND"),
        "task_serializer": "json",
        "accept_content": ["json"],
        "timezone": "UTC",
        "worker_concurrency": 2,
        "task_soft_time_limit": 300,
        "task_hard_time_limit": 600,
        "task_acks_late": True,
        "worker_prefetch_multiplier": 1,
    },
    "flower": {
        "port": 5555,
        "basic_auth": None,
        "url_prefix": "/flower",
    },
    "s3": {
        "endpoint": _ENV_TEST["OPENCASE_S3_ENDPOINT"],
        "access_key": _ENV_TEST["OPENCASE_S3_ACCESS_KEY"],
        "secret_key": _ENV_TEST["OPENCASE_S3_SECRET_KEY"],
        "bucket": _ENV_TEST.get("OPENCASE_S3_BUCKET", "opencase"),
        "use_ssl": False,
        "region": _ENV_TEST.get("OPENCASE_S3_REGION", "us-east-1"),
        "url": f"http://{_ENV_TEST['OPENCASE_S3_ENDPOINT']}",
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


# ---------------------------------------------------------------------------
# RedisSettings — tested directly
# ---------------------------------------------------------------------------


def test_redis_defaults():
    cfg = RedisSettings()
    assert cfg.host == "localhost"  # from .env.test
    assert cfg.port == 6379
    assert cfg.db == 0
    assert cfg.password is None
    assert cfg.ssl is False
    assert cfg.pool_size == 10


def test_redis_url_no_password():
    cfg = RedisSettings()
    assert cfg.url == "redis://localhost:6379/0"


def test_redis_url_with_password(monkeypatch):
    monkeypatch.setenv("OPENCASE_REDIS_PASSWORD", "s3cret")
    cfg = RedisSettings()
    assert cfg.url == "redis://:s3cret@localhost:6379/0"


def test_redis_url_encodes_special_chars(monkeypatch):
    monkeypatch.setenv("OPENCASE_REDIS_PASSWORD", "p@ss/word")
    cfg = RedisSettings()
    assert cfg.url == "redis://:p%40ss%2Fword@localhost:6379/0"


def test_redis_url_ssl(monkeypatch):
    monkeypatch.setenv("OPENCASE_REDIS_SSL", "true")
    cfg = RedisSettings()
    assert cfg.url.startswith("rediss://")


def test_redis_env_override(monkeypatch):
    monkeypatch.setenv("OPENCASE_REDIS_PORT", "6380")
    cfg = RedisSettings()
    assert cfg.port == 6380


def test_redis_prefix_isolation(monkeypatch):
    # OPENCASE_HOST (wrong prefix) must not override OPENCASE_REDIS_HOST
    monkeypatch.setenv("OPENCASE_HOST", "wrong")
    cfg = RedisSettings()
    assert cfg.host != "wrong"


# ---------------------------------------------------------------------------
# CelerySettings — tested directly
# ---------------------------------------------------------------------------


def test_celery_defaults():
    cfg = CelerySettings()
    # broker_url is None at CelerySettings level; the Settings
    # model validator derives it from RedisSettings.
    assert cfg.broker_url is None
    assert cfg.result_backend == _ENV_TEST.get("OPENCASE_CELERY_RESULT_BACKEND")
    assert cfg.task_serializer == "json"
    assert cfg.accept_content == ["json"]
    assert cfg.timezone == "UTC"
    assert cfg.worker_concurrency == 2
    assert cfg.task_soft_time_limit == 300
    assert cfg.task_hard_time_limit == 600
    assert cfg.task_acks_late is True
    assert cfg.worker_prefetch_multiplier == 1


def test_celery_env_override(monkeypatch):
    monkeypatch.setenv("OPENCASE_CELERY_WORKER_CONCURRENCY", "4")
    cfg = CelerySettings()
    assert cfg.worker_concurrency == 4


def test_celery_result_backend_override(monkeypatch):
    dsn = "db+postgresql+psycopg2://user:pass@tasks-db:5432/celery"
    monkeypatch.setenv("OPENCASE_CELERY_RESULT_BACKEND", dsn)
    cfg = CelerySettings()
    assert cfg.result_backend == dsn


def test_celery_prefix_isolation(monkeypatch):
    # OPENCASE_BROKER_URL (wrong prefix) must not override OPENCASE_CELERY_BROKER_URL
    monkeypatch.setenv("OPENCASE_BROKER_URL", "wrong")
    cfg = CelerySettings()
    assert cfg.broker_url != "wrong"


def test_celery_broker_url_derived_from_redis(monkeypatch):
    """Settings derives broker_url from RedisSettings."""
    monkeypatch.delenv("OPENCASE_CELERY_BROKER_URL", raising=False)
    monkeypatch.setenv("OPENCASE_REDIS_HOST", "custom-redis")
    monkeypatch.setenv("OPENCASE_REDIS_PORT", "6380")
    monkeypatch.setenv("OPENCASE_REDIS_DB", "2")
    cfg = Settings()
    assert cfg.celery.broker_url == "redis://custom-redis:6380/2"


def test_celery_broker_url_explicit_overrides_redis(monkeypatch):
    """Explicit OPENCASE_CELERY_BROKER_URL takes precedence over RedisSettings."""
    monkeypatch.setenv("OPENCASE_CELERY_BROKER_URL", "redis://explicit:6379/5")
    monkeypatch.setenv("OPENCASE_REDIS_HOST", "custom-redis")
    cfg = Settings()
    assert cfg.celery.broker_url == "redis://explicit:6379/5"


# ---------------------------------------------------------------------------
# FlowerSettings — tested directly
# ---------------------------------------------------------------------------


def test_flower_defaults():
    cfg = FlowerSettings()
    assert cfg.port == 5555
    assert cfg.basic_auth is None
    assert cfg.url_prefix == "/flower"


def test_flower_env_override(monkeypatch):
    monkeypatch.setenv("OPENCASE_FLOWER_PORT", "5556")
    cfg = FlowerSettings()
    assert cfg.port == 5556


def test_flower_basic_auth(monkeypatch):
    monkeypatch.setenv("OPENCASE_FLOWER_BASIC_AUTH", "admin:secret")
    cfg = FlowerSettings()
    assert cfg.basic_auth == "admin:secret"


def test_flower_prefix_isolation(monkeypatch):
    # OPENCASE_PORT (wrong prefix) must not override OPENCASE_FLOWER_PORT
    monkeypatch.setenv("OPENCASE_PORT", "9999")
    cfg = FlowerSettings()
    assert cfg.port == 5555


# ---------------------------------------------------------------------------
# S3Settings — tested directly
# ---------------------------------------------------------------------------


def test_s3_defaults():
    cfg = S3Settings()
    assert cfg.endpoint == "minio:9000"
    assert cfg.access_key == "opencase"
    assert cfg.secret_key == "changeme"  # noqa: S105
    assert cfg.bucket == "opencase"
    assert cfg.use_ssl is False
    assert cfg.region == "us-east-1"


def test_s3_env_override(monkeypatch):
    monkeypatch.setenv("OPENCASE_S3_BUCKET", "custom-bucket")
    cfg = S3Settings()
    assert cfg.bucket == "custom-bucket"


def test_s3_prefix_isolation(monkeypatch):
    # OPENCASE_ENDPOINT (wrong prefix) must not override OPENCASE_S3_ENDPOINT
    monkeypatch.setenv("OPENCASE_ENDPOINT", "wrong")
    cfg = S3Settings()
    assert cfg.endpoint != "wrong"


def test_s3_missing_access_key_raises(monkeypatch):
    monkeypatch.delenv("OPENCASE_S3_ACCESS_KEY", raising=False)
    with pytest.raises(ValidationError):
        S3Settings()


def test_s3_missing_secret_key_raises(monkeypatch):
    monkeypatch.delenv("OPENCASE_S3_SECRET_KEY", raising=False)
    with pytest.raises(ValidationError):
        S3Settings()


def test_s3_url_http():
    cfg = S3Settings()
    assert cfg.url == "http://minio:9000"


def test_s3_url_https(monkeypatch):
    monkeypatch.setenv("OPENCASE_S3_USE_SSL", "true")
    cfg = S3Settings()
    assert cfg.url == "https://minio:9000"


# ---------------------------------------------------------------------------
# redact_settings
# ---------------------------------------------------------------------------


_REDACTED = "***REDACTED***"


def test_redact_settings_masks_secrets():
    data = {
        "auth": {"secret_key": "real-secret", "algorithm": "HS256"},
        "admin": {"password": "real-pw", "email": "a@b.com"},
        "flower": {"basic_auth": "user:pass", "port": 5555},
        "redis": {"password": "redis-pw", "host": "redis"},
        "celery": {
            "broker_url": "redis://:s3cret@redis:6379/0",
            "result_backend": "db+postgresql+psycopg2://u:p@host/db",
            "timezone": "UTC",
        },
        "s3": {
            "access_key": "AKIAIOSFODNN7EXAMPLE",
            "secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "endpoint": "minio:9000",
            "bucket": "opencase",
        },
    }
    redacted = redact_settings(data)
    assert redacted["auth"]["secret_key"] == _REDACTED
    assert redacted["auth"]["algorithm"] == "HS256"
    assert redacted["admin"]["password"] == _REDACTED
    assert redacted["admin"]["email"] == "a@b.com"
    assert redacted["flower"]["basic_auth"] == _REDACTED
    assert redacted["flower"]["port"] == 5555
    assert redacted["redis"]["password"] == _REDACTED
    assert redacted["redis"]["host"] == "redis"
    # URL fields redact only the password component, not the whole URL
    assert redacted["celery"]["broker_url"] == "redis://:***@redis:6379/0"
    assert (
        redacted["celery"]["result_backend"] == "db+postgresql+psycopg2://u:***@host/db"
    )
    assert redacted["celery"]["timezone"] == "UTC"
    # S3 credentials are redacted
    assert redacted["s3"]["access_key"] == _REDACTED
    assert redacted["s3"]["secret_key"] == _REDACTED
    assert redacted["s3"]["endpoint"] == "minio:9000"
    assert redacted["s3"]["bucket"] == "opencase"


def test_redact_settings_url_without_password():
    data = {"celery": {"broker_url": "redis://redis:6379/0"}}
    redacted = redact_settings(data)
    # No password in URL — passed through unchanged
    assert redacted["celery"]["broker_url"] == "redis://redis:6379/0"


def test_redact_settings_skips_none():
    data = {"redis": {"password": None, "host": "redis"}}
    redacted = redact_settings(data)
    assert redacted["redis"]["password"] is None


def test_redact_settings_recurses_into_lists():
    data = {"items": [{"password": "pw", "name": "a"}, {"host": "b"}]}
    redacted = redact_settings(data)
    assert redacted["items"][0]["password"] == _REDACTED
    assert redacted["items"][0]["name"] == "a"
    assert redacted["items"][1]["host"] == "b"
