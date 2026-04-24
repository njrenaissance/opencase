"""Unit tests for application configuration layered loading.

monkeypatch is used throughout to auto-revert environment variables and
working directory changes after each test, preventing state leakage
between tests (e.g. GIDEON_* env vars or chdir to fixtures/).
"""

import os
from importlib.metadata import version
from pathlib import Path

import pytest
from dotenv import dotenv_values
from pydantic import ValidationError

from app.core.config import (
    DEFAULT_CONTENT_TYPES,
    DEFAULT_EXTENSIONS,
    ApiSettings,
    AuthSettings,
    CelerySettings,
    ChatbotSettings,
    ChunkingSettings,
    DbSettings,
    EmbeddingSettings,
    ExtractionSettings,
    FlowerSettings,
    IngestionSettings,
    QdrantSettings,
    RedisSettings,
    S3Settings,
    Settings,
    redact_settings,
)

# Read required test values from .env.test — single source of truth.
_ENV_TEST = dotenv_values(Path(__file__).parent.parent / ".env.test")

DEFAULTS = {
    "app_name": "Gideon",
    "app_version": version("gideon-backend"),
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
        "service_name": "gideon-api",
        "sample_rate": 1.0,
    },
    "auth": {
        "secret_key": _ENV_TEST["GIDEON_AUTH_SECRET_KEY"],
        "algorithm": "HS256",
        "access_token_expire_minutes": 15,
        "refresh_token_expire_days": 7,
        "totp_issuer": "Gideon",
        "totp_digest": "sha1",
        "totp_window": 1,
        "bcrypt_rounds": 4,
        "login_lockout_attempts": 5,
        "login_lockout_minutes": 15,
    },
    "db": {
        "url": _ENV_TEST["GIDEON_DB_URL"],
        "pool_size": 10,
        "max_overflow": 20,
        "pool_pre_ping": True,
        "echo": False,
    },
    "admin": {
        "email": _ENV_TEST.get("GIDEON_ADMIN_EMAIL"),
        "password": _ENV_TEST.get("GIDEON_ADMIN_PASSWORD"),
        "first_name": _ENV_TEST.get("GIDEON_ADMIN_FIRST_NAME", "Admin"),
        "last_name": _ENV_TEST.get("GIDEON_ADMIN_LAST_NAME", "User"),
        "firm_name": _ENV_TEST.get("GIDEON_ADMIN_FIRM_NAME", "Default Firm"),
    },
    "redis": {
        "host": _ENV_TEST.get("GIDEON_REDIS_HOST", "redis"),
        "port": int(_ENV_TEST.get("GIDEON_REDIS_PORT", "6379")),
        "db": int(_ENV_TEST.get("GIDEON_REDIS_DB", "0")),
        "password": None,
        "ssl": False,
        "pool_size": int(_ENV_TEST.get("GIDEON_REDIS_POOL_SIZE", "10")),
        "url": f"redis://{_ENV_TEST.get('GIDEON_REDIS_HOST', 'redis')}:6379/0",
    },
    "celery": {
        # broker_url is not in .env.test — derived from RedisSettings
        # by the Settings model validator.
        "broker_url": (
            f"redis://{_ENV_TEST.get('GIDEON_REDIS_HOST', 'redis')}"
            f":{_ENV_TEST.get('GIDEON_REDIS_PORT', '6379')}"
            f"/{_ENV_TEST.get('GIDEON_REDIS_DB', '0')}"
        ),
        "result_backend": _ENV_TEST.get("GIDEON_CELERY_RESULT_BACKEND"),
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
        "endpoint": _ENV_TEST["GIDEON_S3_ENDPOINT"],
        "access_key": _ENV_TEST["GIDEON_S3_ACCESS_KEY"],
        "secret_key": _ENV_TEST["GIDEON_S3_SECRET_KEY"],
        "bucket": _ENV_TEST.get("GIDEON_S3_BUCKET", "gideon"),
        "use_ssl": False,
        "region": _ENV_TEST.get("GIDEON_S3_REGION", "us-east-1"),
        "max_upload_bytes": 100 * 1024 * 1024,
        "spool_threshold_bytes": 10 * 1024 * 1024,
        "url": f"http://{_ENV_TEST['GIDEON_S3_ENDPOINT']}",
    },
    "extraction": {
        "tika_url": "http://tika:9998",
        "ocr_enabled": True,
        "ocr_languages": "eng",
        "ocr_language_list": ["eng"],
        "request_timeout": 120,
        "max_file_size_bytes": 100 * 1024 * 1024,
    },
    "ingestion": {
        "allowed_types_file": None,
        "allowed_content_types": DEFAULT_CONTENT_TYPES,
        "allowed_extensions": DEFAULT_EXTENSIONS,
    },
    "chunking": {
        "strategy": "recursive",
        "chunk_size": 3000,
        "chunk_overlap": 600,
        "separators": ["\n\n", "\n", ". ", " ", ""],
    },
    "embedding": {
        "provider": "ollama",
        "model": "nomic-embed-text",
        "base_url": "http://ollama:11434",
        "dimensions": 768,
        "batch_size": 100,
        "request_timeout": 120,
    },
    "chatbot": {
        "system_prompt_file": None,
        "system_prompt": (
            "You are Gideon, a legal discovery assistant for criminal defense"
            " attorneys. "
            "Answer questions based only on the documents retrieved for this"
            " matter. "
            "If the answer is not in the provided context, say so clearly. "
            "Always cite your sources."
        ),
        "model": "tinyllama",
        "temperature": 0.1,
        "max_tokens": 4096,
        "retrieval_chunk_count": 5,
        "base_url": "http://ollama:11434",
        "request_timeout": 120,
    },
    "qdrant": {
        "host": "qdrant",
        "port": 6333,
        "grpc_port": 6334,
        "collection": "gideon_test",
        "prefer_grpc": False,
        "use_ssl": False,
        "api_key": None,
        "url": "http://qdrant:6333",
        "grpc_url": "qdrant:6334",
    },
}

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Remove any GIDEON_ env vars so each test starts clean,
    then reload required fields from .env.test."""
    for key in list(os.environ):
        if key.startswith("GIDEON_"):
            monkeypatch.delenv(key, raising=False)
    for key, value in _ENV_TEST.items():
        if value is not None:
            monkeypatch.setenv(key, value)


def test_defaults():
    cfg = Settings()
    assert cfg.model_dump() == DEFAULTS


def test_env_vars_override_defaults(monkeypatch):
    monkeypatch.setenv("GIDEON_APP_NAME", "TestCase")
    monkeypatch.setenv("GIDEON_DEBUG", "true")
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
    monkeypatch.setenv("GIDEON_APP_NAME", "EnvCase")
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
    monkeypatch.setenv("GIDEON_DEBUG", "false")
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
    monkeypatch.setenv("GIDEON_API_PORT", "9000")
    cfg = ApiSettings()
    assert cfg.port == 9000


# ---------------------------------------------------------------------------
# AuthSettings — tested directly so monkeypatch applies to its own env reads
# ---------------------------------------------------------------------------


def test_auth_missing_secret_key_raises(monkeypatch):
    monkeypatch.delenv("GIDEON_AUTH_SECRET_KEY", raising=False)
    with pytest.raises(ValidationError):
        AuthSettings()


def test_auth_defaults(monkeypatch):
    cfg = AuthSettings()
    assert cfg.algorithm == "HS256"
    assert cfg.access_token_expire_minutes == 15
    assert cfg.refresh_token_expire_days == 7
    assert cfg.totp_issuer == "Gideon"
    assert cfg.totp_window == 1
    assert cfg.totp_digest == "sha1"
    assert cfg.bcrypt_rounds == 4
    assert cfg.login_lockout_attempts == 5
    assert cfg.login_lockout_minutes == 15


def test_auth_env_override(monkeypatch):
    monkeypatch.setenv("GIDEON_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    cfg = AuthSettings()
    assert cfg.access_token_expire_minutes == 30


def test_auth_prefix_isolation(monkeypatch):
    # GIDEON_SECRET_KEY (wrong prefix) must not satisfy GIDEON_AUTH_SECRET_KEY
    monkeypatch.setenv("GIDEON_SECRET_KEY", "wrong")
    monkeypatch.delenv("GIDEON_AUTH_SECRET_KEY", raising=False)
    with pytest.raises(ValidationError):
        AuthSettings()


# ---------------------------------------------------------------------------
# DbSettings — tested directly so monkeypatch applies to its own env reads
# ---------------------------------------------------------------------------


def test_db_missing_url_raises(monkeypatch):
    monkeypatch.delenv("GIDEON_DB_URL", raising=False)
    with pytest.raises(ValidationError):
        DbSettings()


def test_db_defaults(monkeypatch):
    cfg = DbSettings()
    assert cfg.pool_size == 10
    assert cfg.max_overflow == 20
    assert cfg.pool_pre_ping is True
    assert cfg.echo is False


def test_db_env_override(monkeypatch):
    monkeypatch.setenv("GIDEON_DB_POOL_SIZE", "20")
    cfg = DbSettings()
    assert cfg.pool_size == 20


def test_db_prefix_isolation(monkeypatch):
    # GIDEON_URL (wrong prefix) must not satisfy GIDEON_DB_URL
    monkeypatch.setenv("GIDEON_URL", "wrong")
    monkeypatch.delenv("GIDEON_DB_URL", raising=False)
    with pytest.raises(ValidationError):
        DbSettings()


# ---------------------------------------------------------------------------
# RedisSettings — tested directly
# ---------------------------------------------------------------------------


def test_redis_defaults():
    cfg = RedisSettings()
    assert cfg.host == "redis"  # from .env.test
    assert cfg.port == 6379
    assert cfg.db == 0
    assert cfg.password is None
    assert cfg.ssl is False
    assert cfg.pool_size == 10


def test_redis_url_no_password():
    cfg = RedisSettings()
    assert cfg.url == "redis://redis:6379/0"


def test_redis_url_with_password(monkeypatch):
    monkeypatch.setenv("GIDEON_REDIS_PASSWORD", "s3cret")
    cfg = RedisSettings()
    assert cfg.url == "redis://:s3cret@redis:6379/0"


def test_redis_url_encodes_special_chars(monkeypatch):
    monkeypatch.setenv("GIDEON_REDIS_PASSWORD", "p@ss/word")
    cfg = RedisSettings()
    assert cfg.url == "redis://:p%40ss%2Fword@redis:6379/0"


def test_redis_url_ssl(monkeypatch):
    monkeypatch.setenv("GIDEON_REDIS_SSL", "true")
    cfg = RedisSettings()
    assert cfg.url.startswith("rediss://")


def test_redis_env_override(monkeypatch):
    monkeypatch.setenv("GIDEON_REDIS_PORT", "6380")
    cfg = RedisSettings()
    assert cfg.port == 6380


def test_redis_prefix_isolation(monkeypatch):
    # GIDEON_HOST (wrong prefix) must not override GIDEON_REDIS_HOST
    monkeypatch.setenv("GIDEON_HOST", "wrong")
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
    assert cfg.result_backend == _ENV_TEST.get("GIDEON_CELERY_RESULT_BACKEND")
    assert cfg.task_serializer == "json"
    assert cfg.accept_content == ["json"]
    assert cfg.timezone == "UTC"
    assert cfg.worker_concurrency == 2
    assert cfg.task_soft_time_limit == 300
    assert cfg.task_hard_time_limit == 600
    assert cfg.task_acks_late is True
    assert cfg.worker_prefetch_multiplier == 1


def test_celery_env_override(monkeypatch):
    monkeypatch.setenv("GIDEON_CELERY_WORKER_CONCURRENCY", "4")
    cfg = CelerySettings()
    assert cfg.worker_concurrency == 4


def test_celery_result_backend_override(monkeypatch):
    dsn = "db+postgresql+psycopg2://user:pass@tasks-db:5432/celery"
    monkeypatch.setenv("GIDEON_CELERY_RESULT_BACKEND", dsn)
    cfg = CelerySettings()
    assert cfg.result_backend == dsn


def test_celery_prefix_isolation(monkeypatch):
    # GIDEON_BROKER_URL (wrong prefix) must not override GIDEON_CELERY_BROKER_URL
    monkeypatch.setenv("GIDEON_BROKER_URL", "wrong")
    cfg = CelerySettings()
    assert cfg.broker_url != "wrong"


def test_celery_broker_url_derived_from_redis(monkeypatch):
    """Settings derives broker_url from RedisSettings."""
    monkeypatch.delenv("GIDEON_CELERY_BROKER_URL", raising=False)
    monkeypatch.setenv("GIDEON_REDIS_HOST", "custom-redis")
    monkeypatch.setenv("GIDEON_REDIS_PORT", "6380")
    monkeypatch.setenv("GIDEON_REDIS_DB", "2")
    cfg = Settings()
    assert cfg.celery.broker_url == "redis://custom-redis:6380/2"


def test_celery_broker_url_explicit_overrides_redis(monkeypatch):
    """Explicit GIDEON_CELERY_BROKER_URL takes precedence over RedisSettings."""
    monkeypatch.setenv("GIDEON_CELERY_BROKER_URL", "redis://explicit:6379/5")
    monkeypatch.setenv("GIDEON_REDIS_HOST", "custom-redis")
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
    monkeypatch.setenv("GIDEON_FLOWER_PORT", "5556")
    cfg = FlowerSettings()
    assert cfg.port == 5556


def test_flower_basic_auth(monkeypatch):
    monkeypatch.setenv("GIDEON_FLOWER_BASIC_AUTH", "admin:secret")
    cfg = FlowerSettings()
    assert cfg.basic_auth == "admin:secret"


def test_flower_prefix_isolation(monkeypatch):
    # GIDEON_PORT (wrong prefix) must not override GIDEON_FLOWER_PORT
    monkeypatch.setenv("GIDEON_PORT", "9999")
    cfg = FlowerSettings()
    assert cfg.port == 5555


# ---------------------------------------------------------------------------
# S3Settings — tested directly
# ---------------------------------------------------------------------------


def test_s3_defaults():
    cfg = S3Settings()
    assert cfg.endpoint == "minio:9000"
    assert cfg.access_key == "gideon"
    assert cfg.secret_key == "changeme"  # noqa: S105
    assert cfg.bucket == "gideon"
    assert cfg.use_ssl is False
    assert cfg.region == "us-east-1"


def test_s3_env_override(monkeypatch):
    monkeypatch.setenv("GIDEON_S3_BUCKET", "custom-bucket")
    cfg = S3Settings()
    assert cfg.bucket == "custom-bucket"


def test_s3_prefix_isolation(monkeypatch):
    # GIDEON_ENDPOINT (wrong prefix) must not override GIDEON_S3_ENDPOINT
    monkeypatch.setenv("GIDEON_ENDPOINT", "wrong")
    cfg = S3Settings()
    assert cfg.endpoint != "wrong"


def test_s3_missing_access_key_raises(monkeypatch):
    monkeypatch.delenv("GIDEON_S3_ACCESS_KEY", raising=False)
    with pytest.raises(ValidationError):
        S3Settings()


def test_s3_missing_secret_key_raises(monkeypatch):
    monkeypatch.delenv("GIDEON_S3_SECRET_KEY", raising=False)
    with pytest.raises(ValidationError):
        S3Settings()


def test_s3_url_http():
    cfg = S3Settings()
    assert cfg.url == "http://minio:9000"


def test_s3_url_https(monkeypatch):
    monkeypatch.setenv("GIDEON_S3_USE_SSL", "true")
    cfg = S3Settings()
    assert cfg.url == "https://minio:9000"


# ---------------------------------------------------------------------------
# ExtractionSettings — tested directly
# ---------------------------------------------------------------------------


def test_extraction_defaults():
    cfg = ExtractionSettings()
    assert cfg.tika_url == "http://tika:9998"
    assert cfg.ocr_enabled is True
    assert cfg.ocr_languages == "eng"
    assert cfg.ocr_language_list == ["eng"]
    assert cfg.request_timeout == 120
    assert cfg.max_file_size_bytes == 100 * 1024 * 1024


def test_extraction_env_override(monkeypatch):
    monkeypatch.setenv("GIDEON_EXTRACTION_TIKA_URL", "http://custom:8080")
    cfg = ExtractionSettings()
    assert cfg.tika_url == "http://custom:8080"


def test_extraction_prefix_isolation(monkeypatch):
    # GIDEON_TIKA_URL (wrong prefix) must not override GIDEON_EXTRACTION_TIKA_URL
    monkeypatch.setenv("GIDEON_TIKA_URL", "wrong")
    cfg = ExtractionSettings()
    assert cfg.tika_url != "wrong"


def test_extraction_ocr_languages_comma_separated(monkeypatch):
    monkeypatch.setenv("GIDEON_EXTRACTION_OCR_LANGUAGES", "eng,fra,deu")
    cfg = ExtractionSettings()
    assert cfg.ocr_languages == "eng,fra,deu"
    assert cfg.ocr_language_list == ["eng", "fra", "deu"]


# ---------------------------------------------------------------------------
# IngestionSettings — tested directly
# ---------------------------------------------------------------------------


def test_ingestion_defaults():
    cfg = IngestionSettings()
    assert cfg.allowed_types_file is None
    assert cfg.allowed_content_types == DEFAULT_CONTENT_TYPES
    assert cfg.allowed_extensions == DEFAULT_EXTENSIONS


def test_ingestion_custom_types_file(tmp_path):
    f = tmp_path / "types.txt"
    f.write_text(
        "# Custom types\napplication/pdf\ntext/plain\n.pdf\n.txt\n",
        encoding="utf-8",
    )
    cfg = IngestionSettings(allowed_types_file=f)
    assert cfg.allowed_content_types == frozenset({"application/pdf", "text/plain"})
    assert cfg.allowed_extensions == frozenset({".pdf", ".txt"})


def test_ingestion_missing_file_raises(tmp_path):
    with pytest.raises(ValidationError):
        IngestionSettings(allowed_types_file=tmp_path / "nonexistent.txt")


def test_ingestion_empty_file_raises(tmp_path):
    f = tmp_path / "empty.txt"
    f.write_text("# only comments\n\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="no valid"):
        IngestionSettings(allowed_types_file=f)


def test_ingestion_prefix_isolation(monkeypatch):
    # GIDEON_ALLOWED_TYPES_FILE (wrong prefix) must not override
    monkeypatch.setenv("GIDEON_ALLOWED_TYPES_FILE", "/tmp/wrong.txt")  # noqa: S108
    cfg = IngestionSettings()
    assert cfg.allowed_types_file is None


# ---------------------------------------------------------------------------
# ChunkingSettings — tested directly
# ---------------------------------------------------------------------------


def test_chunking_defaults():
    cfg = ChunkingSettings()
    assert cfg.strategy == "recursive"
    assert cfg.chunk_size == 3000
    assert cfg.chunk_overlap == 600
    assert cfg.separators == ["\n\n", "\n", ". ", " ", ""]


def test_chunking_env_override(monkeypatch):
    monkeypatch.setenv("GIDEON_CHUNKING_CHUNK_SIZE", "5000")
    cfg = ChunkingSettings()
    assert cfg.chunk_size == 5000


def test_chunking_prefix_isolation(monkeypatch):
    # GIDEON_CHUNK_SIZE (wrong prefix) must not override GIDEON_CHUNKING_CHUNK_SIZE
    monkeypatch.setenv("GIDEON_CHUNK_SIZE", "999")
    cfg = ChunkingSettings()
    assert cfg.chunk_size == 3000


@pytest.mark.parametrize(
    "overlap,size",
    [(1000, 1000), (1500, 1000)],
    ids=["equal", "exceeds"],
)
def test_chunking_overlap_gte_size_raises(monkeypatch, overlap, size):
    monkeypatch.setenv("GIDEON_CHUNKING_CHUNK_OVERLAP", str(overlap))
    monkeypatch.setenv("GIDEON_CHUNKING_CHUNK_SIZE", str(size))
    with pytest.raises(ValidationError, match="chunk_overlap"):
        ChunkingSettings()


def test_chunking_zero_overlap_valid(monkeypatch):
    monkeypatch.setenv("GIDEON_CHUNKING_CHUNK_OVERLAP", "0")
    cfg = ChunkingSettings()
    assert cfg.chunk_overlap == 0


# ---------------------------------------------------------------------------
# EmbeddingSettings — tested directly
# ---------------------------------------------------------------------------


def test_embedding_defaults():
    cfg = EmbeddingSettings()
    assert cfg.model_dump() == DEFAULTS["embedding"]


def test_embedding_env_override(monkeypatch):
    monkeypatch.setenv("GIDEON_EMBEDDING_MODEL", "mxbai-embed-large")
    cfg = EmbeddingSettings()
    assert cfg.model == "mxbai-embed-large"


def test_embedding_prefix_isolation(monkeypatch):
    # GIDEON_MODEL (wrong prefix) must not override GIDEON_EMBEDDING_MODEL
    monkeypatch.setenv("GIDEON_MODEL", "wrong")
    cfg = EmbeddingSettings()
    assert cfg.model == "nomic-embed-text"


# ---------------------------------------------------------------------------
# ChatbotSettings — tested directly
# ---------------------------------------------------------------------------


def test_chatbot_defaults():
    cfg = ChatbotSettings()
    assert cfg.model_dump() == DEFAULTS["chatbot"]


def test_chatbot_env_override(monkeypatch):
    monkeypatch.setenv("GIDEON_CHATBOT_MODEL", "mistral")
    cfg = ChatbotSettings()
    assert cfg.model == "mistral"


def test_chatbot_prefix_isolation(monkeypatch):
    # GIDEON_MODEL (wrong prefix) must not override GIDEON_CHATBOT_MODEL
    monkeypatch.setenv("GIDEON_MODEL", "wrong")
    cfg = ChatbotSettings()
    assert cfg.model == "tinyllama"


def test_chatbot_system_prompt_override(monkeypatch):
    monkeypatch.setenv("GIDEON_CHATBOT_SYSTEM_PROMPT", "Custom legal prompt.")
    cfg = ChatbotSettings()
    assert cfg.system_prompt == "Custom legal prompt."


def test_chatbot_system_prompt_file_loads_content(tmp_path, monkeypatch):
    prompt_file = tmp_path / "system_prompt.md"
    prompt_file.write_text("Custom prompt from file.", encoding="utf-8")
    monkeypatch.setenv("GIDEON_CHATBOT_SYSTEM_PROMPT_FILE", str(prompt_file))
    cfg = ChatbotSettings()
    assert cfg.system_prompt == "Custom prompt from file."
    assert cfg.system_prompt_file == prompt_file


def test_chatbot_system_prompt_file_missing_raises(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "GIDEON_CHATBOT_SYSTEM_PROMPT_FILE", str(tmp_path / "nonexistent.md")
    )
    with pytest.raises(ValidationError, match="non-existent"):
        ChatbotSettings()


def test_chatbot_system_prompt_file_empty_raises(tmp_path, monkeypatch):
    prompt_file = tmp_path / "empty.md"
    prompt_file.write_text("   \n\n", encoding="utf-8")
    monkeypatch.setenv("GIDEON_CHATBOT_SYSTEM_PROMPT_FILE", str(prompt_file))
    with pytest.raises(ValidationError, match="empty"):
        ChatbotSettings()


def test_chatbot_temperature_boundaries_valid(monkeypatch):
    monkeypatch.setenv("GIDEON_CHATBOT_TEMPERATURE", "0.0")
    cfg = ChatbotSettings()
    assert cfg.temperature == pytest.approx(0.0)

    monkeypatch.setenv("GIDEON_CHATBOT_TEMPERATURE", "2.0")
    cfg2 = ChatbotSettings()
    assert cfg2.temperature == pytest.approx(2.0)


def test_chatbot_chunk_count_boundaries_valid(monkeypatch):
    monkeypatch.setenv("GIDEON_CHATBOT_RETRIEVAL_CHUNK_COUNT", "1")
    cfg = ChatbotSettings()
    assert cfg.retrieval_chunk_count == 1

    monkeypatch.setenv("GIDEON_CHATBOT_RETRIEVAL_CHUNK_COUNT", "20")
    cfg2 = ChatbotSettings()
    assert cfg2.retrieval_chunk_count == 20


@pytest.mark.parametrize(
    "env_var,value",
    [
        ("GIDEON_CHATBOT_TEMPERATURE", "-0.1"),
        ("GIDEON_CHATBOT_TEMPERATURE", "2.1"),
        ("GIDEON_CHATBOT_MAX_TOKENS", "0"),
        ("GIDEON_CHATBOT_MAX_TOKENS", "-1"),
        ("GIDEON_CHATBOT_RETRIEVAL_CHUNK_COUNT", "0"),
        ("GIDEON_CHATBOT_RETRIEVAL_CHUNK_COUNT", "21"),
    ],
    ids=[
        "temperature-below-min",
        "temperature-above-max",
        "max_tokens-zero",
        "max_tokens-negative",
        "chunk_count-zero",
        "chunk_count-above-max",
    ],
)
def test_chatbot_validation_failures(monkeypatch, env_var, value):
    monkeypatch.setenv(env_var, value)
    with pytest.raises(ValidationError):
        ChatbotSettings()


def test_chatbot_present_on_settings():
    cfg = Settings()
    assert isinstance(cfg.chatbot, ChatbotSettings)
    assert cfg.chatbot.model == "tinyllama"


# ---------------------------------------------------------------------------
# QdrantSettings — tested directly
# ---------------------------------------------------------------------------


def test_qdrant_defaults():
    cfg = QdrantSettings()
    assert cfg.model_dump() == DEFAULTS["qdrant"]


def test_qdrant_env_override(monkeypatch):
    monkeypatch.setenv("GIDEON_QDRANT_HOST", "custom-qdrant")
    cfg = QdrantSettings()
    assert cfg.host == "custom-qdrant"


def test_qdrant_prefix_isolation(monkeypatch):
    # GIDEON_HOST (wrong prefix) must not override GIDEON_QDRANT_HOST
    monkeypatch.setenv("GIDEON_HOST", "wrong")
    cfg = QdrantSettings()
    assert cfg.host == "qdrant"


def test_qdrant_url_computed():
    cfg = QdrantSettings()
    assert cfg.url == "http://qdrant:6333"


def test_qdrant_url_custom_host_port(monkeypatch):
    monkeypatch.setenv("GIDEON_QDRANT_HOST", "my-qdrant")
    monkeypatch.setenv("GIDEON_QDRANT_PORT", "7333")
    cfg = QdrantSettings()
    assert cfg.url == "http://my-qdrant:7333"


def test_qdrant_url_https(monkeypatch):
    monkeypatch.setenv("GIDEON_QDRANT_USE_SSL", "true")
    cfg = QdrantSettings()
    assert cfg.url == "https://qdrant:6333"


def test_qdrant_grpc_url_computed():
    cfg = QdrantSettings()
    assert cfg.grpc_url == "qdrant:6334"


def test_qdrant_grpc_url_custom(monkeypatch):
    monkeypatch.setenv("GIDEON_QDRANT_HOST", "my-qdrant")
    monkeypatch.setenv("GIDEON_QDRANT_GRPC_PORT", "7334")
    cfg = QdrantSettings()
    assert cfg.grpc_url == "my-qdrant:7334"


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
            "bucket": "gideon",
        },
        "qdrant": {
            "api_key": "secret-qdrant-key",
            "host": "qdrant",
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
    assert redacted["s3"]["bucket"] == "gideon"
    # Qdrant API key is redacted
    assert redacted["qdrant"]["api_key"] == _REDACTED
    assert redacted["qdrant"]["host"] == "qdrant"


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
