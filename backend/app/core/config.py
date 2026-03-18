from importlib.metadata import version
from typing import Any, Literal

from pydantic import Field
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
    otel: OtelSettings = OtelSettings()
    api: ApiSettings = ApiSettings()
    auth: AuthSettings = AuthSettings()  # type: ignore[call-arg]
    db: DbSettings = DbSettings()  # type: ignore[call-arg]

    model_config = SettingsConfigDict(
        env_prefix="OPENCASE_",
        env_file=".env",
        env_file_encoding="utf-8",
        json_file="config.json",
        json_file_encoding="utf-8",
        # "ignore" lets FastAPI receive admin-seed env vars (OPENCASE_ADMIN_*)
        # without validation errors. Trade-off: typos in OPENCASE_* vars are
        # silently ignored rather than raising at startup.
        extra="ignore",
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
