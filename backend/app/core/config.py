from importlib.metadata import version
from typing import Any, Literal
from urllib.parse import quote, urlparse

from pydantic import Field, computed_field, model_validator
from pydantic_settings import (
    BaseSettings,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class OtelSettings(BaseSettings):
    """OpenTelemetry sub-config (OPENCASE_OTEL_ prefix)."""

    enabled: bool = False
    exporter: Literal["console", "otlp"] = "console"
    endpoint: str = "http://localhost:4318"
    service_name: str = "opencase-api"
    sample_rate: float = 1.0

    model_config = SettingsConfigDict(env_prefix="OPENCASE_OTEL_")


class AuthSettings(BaseSettings):
    """Authentication sub-config (OPENCASE_AUTH_ prefix).

    secret_key is required — the application will not start without it.
    Generate a suitable value with: openssl rand -base64 32
    """

    secret_key: str = Field(..., min_length=1)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    totp_issuer: str = "OpenCase"
    totp_digest: Literal["sha1", "sha256", "sha512"] = "sha1"
    totp_window: int = 1
    bcrypt_rounds: int = 12
    login_lockout_attempts: int = 5
    login_lockout_minutes: int = 15

    model_config = SettingsConfigDict(env_prefix="OPENCASE_AUTH_")


class DbSettings(BaseSettings):
    """Database sub-config (OPENCASE_DB_ prefix).

    url is required — the application will not start without it.
    Example: postgresql+asyncpg://user:password@localhost:5432/opencase
    """

    url: str = Field(..., min_length=1)
    pool_size: int = 10
    max_overflow: int = 20
    pool_pre_ping: bool = True
    echo: bool = False

    model_config = SettingsConfigDict(env_prefix="OPENCASE_DB_")


class ApiSettings(BaseSettings):
    """HTTP server sub-config (OPENCASE_API_ prefix).

    Controls the address and port uvicorn binds to inside the container.
    Override via OPENCASE_API_HOST and OPENCASE_API_PORT environment variables.
    """

    host: str = "0.0.0.0"  # noqa: S104 — bind all interfaces inside container
    port: int = 8000

    model_config = SettingsConfigDict(env_prefix="OPENCASE_API_")


class AdminSettings(BaseSettings):
    """Admin seed sub-config (OPENCASE_ADMIN_ prefix).

    When email and password are set, the FastAPI lifespan hook creates the
    initial admin user on every startup (idempotent).
    """

    email: str | None = None
    password: str | None = None
    first_name: str = "Admin"
    last_name: str = "User"
    firm_name: str = "Default Firm"

    model_config = SettingsConfigDict(env_prefix="OPENCASE_ADMIN_")


class RedisSettings(BaseSettings):
    """Redis sub-config (OPENCASE_REDIS_ prefix).

    Individual fields are preferred over a monolithic URL so that each
    component is independently overridable and visible in documentation.
    The computed ``url`` property assembles them into a connection string.
    """

    host: str = "redis"
    port: int = 6379
    db: int = 0
    password: str | None = None
    ssl: bool = False
    pool_size: int = 10

    @computed_field  # type: ignore[prop-decorator]
    @property
    def url(self) -> str:
        scheme = "rediss" if self.ssl else "redis"
        auth = f":{quote(self.password, safe='')}@" if self.password else ""
        return f"{scheme}://{auth}{self.host}:{self.port}/{self.db}"

    model_config = SettingsConfigDict(env_prefix="OPENCASE_REDIS_")


class CelerySettings(BaseSettings):
    """Celery sub-config (OPENCASE_CELERY_ prefix).

    When ``broker_url`` is not set via ``OPENCASE_CELERY_BROKER_URL``,
    it is derived from ``RedisSettings.url`` by the parent ``Settings``
    model validator — so changing ``OPENCASE_REDIS_*`` fields automatically
    updates the broker address.

    result_backend is None until the tasks database is provisioned
    (Feature 2.4).
    """

    broker_url: str | None = None
    result_backend: str | None = None
    task_serializer: str = "json"
    accept_content: list[str] = Field(default_factory=lambda: ["json"])
    timezone: str = "UTC"
    worker_concurrency: int = 2
    task_soft_time_limit: int = 300
    task_hard_time_limit: int = 600
    task_acks_late: bool = True
    worker_prefetch_multiplier: int = 1

    model_config = SettingsConfigDict(env_prefix="OPENCASE_CELERY_")


class FlowerSettings(BaseSettings):
    """Flower monitoring UI sub-config (OPENCASE_FLOWER_ prefix)."""

    port: int = 5555
    basic_auth: str | None = None
    url_prefix: str = "/flower"

    model_config = SettingsConfigDict(env_prefix="OPENCASE_FLOWER_")


class S3Settings(BaseSettings):
    """S3-compatible object storage sub-config (OPENCASE_S3_ prefix).

    Targets MinIO running inside the Docker network. The computed ``url``
    property assembles http(s)://endpoint for SDK clients.
    """

    endpoint: str = Field("minio:9000", min_length=1)
    access_key: str = Field(..., min_length=1)
    secret_key: str = Field(..., min_length=1)
    bucket: str = "opencase"
    use_ssl: bool = False
    region: str = "us-east-1"
    max_upload_bytes: int = Field(100 * 1024 * 1024, gt=0)  # 100 MB
    spool_threshold_bytes: int = Field(10 * 1024 * 1024, gt=0)  # 10 MB

    @model_validator(mode="after")
    def _validate_spool_threshold(self) -> "S3Settings":
        if self.spool_threshold_bytes > self.max_upload_bytes:
            msg = (
                f"spool_threshold_bytes ({self.spool_threshold_bytes}) must not"
                f" exceed max_upload_bytes ({self.max_upload_bytes})"
            )
            raise ValueError(msg)
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def url(self) -> str:
        scheme = "https" if self.use_ssl else "http"
        return f"{scheme}://{self.endpoint}"

    model_config = SettingsConfigDict(env_prefix="OPENCASE_S3_")


# ---------------------------------------------------------------------------
# Secret redaction
# ---------------------------------------------------------------------------

_SECRET_SUBSTRINGS = ("password", "secret")
# access_key: covers S3Settings.access_key (MinIO credentials).
# If a future settings class reuses this field name for a non-secret
# value, move redaction into a per-class allowlist instead.
_SECRET_EXACT = frozenset({"basic_auth", "access_key"})
_URL_FIELDS = frozenset({"broker_url", "result_backend", "url"})


def _redact_url(value: str) -> str:
    """Redact only the password component of a URL, preserving host/port/path."""
    try:
        parsed = urlparse(value)
    except Exception:
        return "***REDACTED***"
    if parsed.password:
        replaced = parsed.netloc.replace(f":{parsed.password}@", ":***@")
        return parsed._replace(netloc=replaced).geturl()
    return value


def redact_settings(data: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of a nested settings dict with sensitive values masked."""
    out: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            out[key] = redact_settings(value)
        elif isinstance(value, list):
            out[key] = [
                redact_settings(item) if isinstance(item, dict) else item
                for item in value
            ]
        elif value is not None and (
            any(s in key.lower() for s in _SECRET_SUBSTRINGS)
            or key.lower() in _SECRET_EXACT
        ):
            out[key] = "***REDACTED***"
        elif isinstance(value, str) and key.lower() in _URL_FIELDS:
            out[key] = _redact_url(value)
        else:
            out[key] = value
    return out


class Settings(BaseSettings):
    """Application settings with layered loading.

    Priority (highest wins):
      1. Environment variables (OPENCASE_ prefix)
      2. .env file
      3. config.json file
      4. Hard-coded defaults
    """

    app_name: str = "OpenCase"
    app_version: str = version("opencase")
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_output: Literal["stdout", "stderr"] = "stdout"
    deployment_mode: str = "airgapped"
    otel: OtelSettings = Field(default_factory=OtelSettings)
    api: ApiSettings = Field(default_factory=ApiSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)  # type: ignore[arg-type]
    db: DbSettings = Field(default_factory=DbSettings)  # type: ignore[arg-type]
    admin: AdminSettings = Field(default_factory=AdminSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    celery: CelerySettings = Field(default_factory=CelerySettings)
    flower: FlowerSettings = Field(default_factory=FlowerSettings)
    # S3Settings has required fields (access_key, secret_key) that are
    # satisfied by env vars at startup, same pattern as auth/db.
    s3: S3Settings = Field(default_factory=S3Settings)  # type: ignore[arg-type]

    @model_validator(mode="after")
    def _derive_celery_broker_url(self) -> "Settings":
        """Default broker_url to redis.url when not explicitly set."""
        if self.celery.broker_url is None:
            self.celery.broker_url = self.redis.url
        return self

    model_config = SettingsConfigDict(
        env_prefix="OPENCASE_",
        env_file=".env",
        env_file_encoding="utf-8",
        json_file="config.json",
        json_file_encoding="utf-8",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,  # noqa: ARG003 — no secrets dir used
        **kwargs: Any,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            env_settings,
            dotenv_settings,
            JsonConfigSettingsSource(settings_cls),
            init_settings,  # allows Settings(field=val) for testing
        )


settings = Settings()
