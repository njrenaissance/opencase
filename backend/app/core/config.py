import logging
import re
from importlib.metadata import version
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote, urlparse

from pydantic import Field, computed_field, model_validator
from pydantic_settings import (
    BaseSettings,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

logger = logging.getLogger(__name__)


class OtelSettings(BaseSettings):
    """OpenTelemetry sub-config (GIDEON_OTEL_ prefix)."""

    enabled: bool = False
    exporter: Literal["console", "otlp"] = "console"
    endpoint: str = "http://localhost:4318"
    service_name: str = "gideon-api"
    sample_rate: float = 1.0

    model_config = SettingsConfigDict(env_prefix="GIDEON_OTEL_")


class AuthSettings(BaseSettings):
    """Authentication sub-config (GIDEON_AUTH_ prefix).

    secret_key is required — the application will not start without it.
    Generate a suitable value with: openssl rand -base64 32
    """

    secret_key: str = Field(..., min_length=1)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    totp_issuer: str = "Gideon"
    totp_digest: Literal["sha1", "sha256", "sha512"] = "sha1"
    totp_window: int = 1
    bcrypt_rounds: int = 12
    login_lockout_attempts: int = 5
    login_lockout_minutes: int = 15

    model_config = SettingsConfigDict(env_prefix="GIDEON_AUTH_")


class DbSettings(BaseSettings):
    """Database sub-config (GIDEON_DB_ prefix).

    url is required — the application will not start without it.
    Example: postgresql+asyncpg://user:password@localhost:5432/gideon
    """

    url: str = Field(..., min_length=1)
    pool_size: int = 10
    max_overflow: int = 20
    pool_pre_ping: bool = True
    echo: bool = False

    model_config = SettingsConfigDict(env_prefix="GIDEON_DB_")


class ApiSettings(BaseSettings):
    """HTTP server sub-config (GIDEON_API_ prefix).

    Controls the address and port uvicorn binds to inside the container.
    Override via GIDEON_API_HOST and GIDEON_API_PORT environment variables.
    """

    host: str = "0.0.0.0"  # noqa: S104 — bind all interfaces inside container
    port: int = 8000

    model_config = SettingsConfigDict(env_prefix="GIDEON_API_")


class AdminSettings(BaseSettings):
    """Admin seed sub-config (GIDEON_ADMIN_ prefix).

    When email and password are set, the FastAPI lifespan hook creates the
    initial admin user on every startup (idempotent).
    """

    email: str | None = None
    password: str | None = None
    first_name: str = "Admin"
    last_name: str = "User"
    firm_name: str = "Default Firm"

    model_config = SettingsConfigDict(env_prefix="GIDEON_ADMIN_")


class RedisSettings(BaseSettings):
    """Redis sub-config (GIDEON_REDIS_ prefix).

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

    model_config = SettingsConfigDict(env_prefix="GIDEON_REDIS_")


class CelerySettings(BaseSettings):
    """Celery sub-config (GIDEON_CELERY_ prefix).

    When ``broker_url`` is not set via ``GIDEON_CELERY_BROKER_URL``,
    it is derived from ``RedisSettings.url`` by the parent ``Settings``
    model validator — so changing ``GIDEON_REDIS_*`` fields automatically
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

    model_config = SettingsConfigDict(env_prefix="GIDEON_CELERY_")


class FlowerSettings(BaseSettings):
    """Flower monitoring UI sub-config (GIDEON_FLOWER_ prefix)."""

    port: int = 5555
    basic_auth: str | None = None
    url_prefix: str = "/flower"

    model_config = SettingsConfigDict(env_prefix="GIDEON_FLOWER_")


class S3Settings(BaseSettings):
    """S3-compatible object storage sub-config (GIDEON_S3_ prefix).

    Targets MinIO running inside the Docker network. The computed ``url``
    property assembles http(s)://endpoint for SDK clients.
    """

    endpoint: str = Field("minio:9000", min_length=1)
    access_key: str = Field(..., min_length=1)
    secret_key: str = Field(..., min_length=1)
    bucket: str = "gideon"
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

    model_config = SettingsConfigDict(env_prefix="GIDEON_S3_")


class ExtractionSettings(BaseSettings):
    """Document extraction sub-config (GIDEON_EXTRACTION_ prefix).

    Configures Apache Tika text extraction and Tesseract OCR for the
    ingestion pipeline.
    """

    tika_url: str = "http://tika:9998"
    ocr_enabled: bool = True
    ocr_languages: str = "eng"
    request_timeout: int = Field(120, gt=0)
    max_file_size_bytes: int = Field(100 * 1024 * 1024, gt=0)  # 100 MB

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ocr_language_list(self) -> list[str]:
        """Parse comma-separated language codes into a list."""
        return [lang.strip() for lang in self.ocr_languages.split(",") if lang.strip()]

    model_config = SettingsConfigDict(env_prefix="GIDEON_EXTRACTION_")


class ChunkingSettings(BaseSettings):
    """Text chunking sub-config (GIDEON_CHUNKING_ prefix).

    Controls how extracted document text is split into chunks for
    embedding and vector search.  The default strategy uses recursive
    character splitting with the given separators.
    """

    strategy: Literal["recursive"] = "recursive"
    chunk_size: int = Field(1000, gt=0)
    chunk_overlap: int = Field(200, ge=0)
    separators: list[str] = Field(default_factory=lambda: ["\n\n", "\n", ". ", " ", ""])

    @model_validator(mode="after")
    def _validate_overlap_less_than_size(self) -> "ChunkingSettings":
        if self.chunk_overlap >= self.chunk_size:
            msg = (
                f"chunk_overlap ({self.chunk_overlap}) must be less than"
                f" chunk_size ({self.chunk_size})"
            )
            raise ValueError(msg)
        return self

    model_config = SettingsConfigDict(env_prefix="GIDEON_CHUNKING_")


class EmbeddingSettings(BaseSettings):
    """Embedding generation sub-config (GIDEON_EMBEDDING_ prefix).

    Controls which embedding provider and model are used to vectorize
    document chunks.  Only Ollama is supported (airgapped deployment).
    """

    provider: Literal["ollama"] = "ollama"
    model: str = "nomic-embed-text"
    base_url: str = "http://ollama:11434"
    dimensions: int = Field(768, gt=0)
    batch_size: int = Field(100, gt=0)
    request_timeout: int = Field(120, gt=0)

    model_config = SettingsConfigDict(env_prefix="GIDEON_EMBEDDING_")


_CHATBOT_DEFAULT_SYSTEM_PROMPT = (
    "You are Gideon, a legal discovery assistant for criminal defense attorneys. "
    "Answer questions based only on the documents retrieved for this matter. "
    "If the answer is not in the provided context, say so clearly. "
    "Always cite your sources."
)


class ChatbotSettings(BaseSettings):
    """Chatbot / LLM inference sub-config (GIDEON_CHATBOT_ prefix).

    Configures the inference model and generation parameters used by the
    RAG chatbot.  The model name is the single source of truth for which
    Ollama model is pulled at container startup (ollama-init service).

    Temperature is intentionally low (0.1) — legal Q&A requires deterministic,
    consistent answers, not creative variation.

    System prompt loading priority:
      1. GIDEON_CHATBOT_SYSTEM_PROMPT_FILE — path to a Markdown file (richest option)
      2. GIDEON_CHATBOT_SYSTEM_PROMPT — inline string override
      3. Built-in default (_CHATBOT_DEFAULT_SYSTEM_PROMPT)

    The canonical editable prompt lives at backend/SYSTEM_PROMPT.md.
    In production, set GIDEON_CHATBOT_SYSTEM_PROMPT_FILE=/app/SYSTEM_PROMPT.md.
    """

    system_prompt_file: Path | None = None
    system_prompt: str = _CHATBOT_DEFAULT_SYSTEM_PROMPT
    model: str = "llama3"
    temperature: float = Field(0.1, ge=0.0, le=2.0)
    max_tokens: int = Field(4096, gt=0)
    retrieval_chunk_count: int = Field(5, ge=1, le=20)
    base_url: str = "http://ollama:11434"
    request_timeout: int = Field(120, gt=0)

    model_config = SettingsConfigDict(env_prefix="GIDEON_CHATBOT_", extra="ignore")

    @model_validator(mode="after")
    def _load_system_prompt_from_file(self) -> "ChatbotSettings":
        """If system_prompt_file is set, read the file and use its content."""
        if self.system_prompt_file is not None:
            path = self.system_prompt_file
            if not path.exists():
                raise ValueError(
                    f"GIDEON_CHATBOT_SYSTEM_PROMPT_FILE points to a non-existent "
                    f"file: {path}"
                )
            content = path.read_text(encoding="utf-8").strip()
            if not content:
                raise ValueError(f"GIDEON_CHATBOT_SYSTEM_PROMPT_FILE is empty: {path}")
            object.__setattr__(self, "system_prompt", content)
        return self


class QdrantSettings(BaseSettings):
    """Qdrant vector store sub-config (GIDEON_QDRANT_ prefix).

    Connection settings for the Qdrant vector database, analogous to
    S3Settings for MinIO — vendor-specific because it's an external
    service connection.
    """

    host: str = "qdrant"
    port: int = 6333
    grpc_port: int = 6334
    collection: str = "gideon"
    prefer_grpc: bool = True
    use_ssl: bool = False
    api_key: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def url(self) -> str:
        """REST API URL (always HTTP/HTTPS)."""
        scheme = "https" if self.use_ssl else "http"
        return f"{scheme}://{self.host}:{self.port}"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def grpc_url(self) -> str:
        """gRPC endpoint address (host:grpc_port, no scheme)."""
        return f"{self.host}:{self.grpc_port}"

    model_config = SettingsConfigDict(env_prefix="GIDEON_QDRANT_")


# ---------------------------------------------------------------------------
# Ingestion defaults
# ---------------------------------------------------------------------------

_MIME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9!#$&\-^_]+/[a-zA-Z0-9!#$&\-^_.+]+$")

DEFAULT_CONTENT_TYPES = frozenset(
    {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/rtf",
        "text/plain",
        "text/markdown",
        "text/csv",
        "text/html",
        "image/jpeg",
        "image/png",
        "image/tiff",
        "image/gif",
        "image/bmp",
        "image/webp",
        "application/octet-stream",
    }
)

DEFAULT_EXTENSIONS = frozenset(
    {
        ".pdf",
        ".doc",
        ".docx",
        ".xlsx",
        ".pptx",
        ".rtf",
        ".txt",
        ".md",
        ".csv",
        ".html",
        ".htm",
        ".jpg",
        ".jpeg",
        ".png",
        ".tiff",
        ".tif",
        ".gif",
        ".bmp",
        ".webp",
    }
)


def _parse_allowed_types_file(
    path: Path,
) -> tuple[frozenset[str], frozenset[str]]:
    """Parse a flat file into (mime_types, extensions).

    Raises ``ValueError`` on missing file, empty result, or invalid entries.
    """
    if not path.is_file():
        msg = f"allowed_types_file not found: {path}"
        raise ValueError(msg)
    entries = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    mime_types: list[str] = []
    extensions: list[str] = []
    for entry in entries:
        if "/" in entry:
            if not _MIME_RE.match(entry):
                logger.warning(
                    "Ignoring invalid MIME type in %s: %r",
                    path,
                    entry,
                )
                continue
            mime_types.append(entry)
        elif entry.startswith(".") and len(entry) > 1:
            extensions.append(entry)
        else:
            logger.warning(
                "Ignoring unrecognized entry in %s: %r"
                " (expected MIME type with '/' or extension with '.')",
                path,
                entry,
            )
    if not mime_types and not extensions:
        msg = f"allowed_types_file {path} contains no valid MIME types or extensions"
        raise ValueError(msg)
    return frozenset(mime_types), frozenset(extensions)


class IngestionSettings(BaseSettings):
    """Ingestion pipeline sub-config (GIDEON_INGESTION_ prefix).

    Controls which document types are accepted for upload and bulk-ingest.
    When ``allowed_types_file`` is set, MIME types and file extensions are
    loaded from the flat file (one entry per line, ``#`` comments allowed).
    Otherwise built-in defaults are used.

    All authenticated users can read this config via
    ``GET /documents/ingestion-config`` — the CLI needs it to filter
    files during bulk-ingest before uploading.
    """

    allowed_types_file: Path | None = None
    allowed_content_types: frozenset[str] = DEFAULT_CONTENT_TYPES
    allowed_extensions: frozenset[str] = DEFAULT_EXTENSIONS

    @model_validator(mode="before")
    @classmethod
    def _load_allowed_types(cls, values: dict[str, Any]) -> dict[str, Any]:
        path = values.get("allowed_types_file")
        if path is None:
            return values
        if not isinstance(path, Path):
            path = Path(path)
        mime_types, extensions = _parse_allowed_types_file(path)
        values["allowed_content_types"] = mime_types
        values["allowed_extensions"] = extensions
        return values

    model_config = SettingsConfigDict(env_prefix="GIDEON_INGESTION_")


# ---------------------------------------------------------------------------
# Secret redaction
# ---------------------------------------------------------------------------

_SECRET_SUBSTRINGS = ("password", "secret")
# access_key: S3Settings (MinIO), api_key: QdrantSettings.
# If a future settings class reuses one of these field names for a
# non-secret value, move redaction into a per-class allowlist instead.
_SECRET_EXACT = frozenset({"basic_auth", "access_key", "api_key"})
# _redact_url only masks the password component of URLs — credential-free
# URLs (e.g. QdrantSettings.url, S3Settings.url) pass through unchanged.
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
      1. Environment variables (GIDEON_ prefix)
      2. .env file
      3. config.json file
      4. Hard-coded defaults
    """

    app_name: str = "Gideon"
    app_version: str = version("gideon")
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
    extraction: ExtractionSettings = Field(default_factory=ExtractionSettings)  # type: ignore[arg-type]
    ingestion: IngestionSettings = Field(default_factory=IngestionSettings)
    chunking: ChunkingSettings = Field(default_factory=ChunkingSettings)  # type: ignore[arg-type]
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)  # type: ignore[arg-type]
    chatbot: ChatbotSettings = Field(default_factory=ChatbotSettings)  # type: ignore[arg-type]
    qdrant: QdrantSettings = Field(default_factory=QdrantSettings)

    @model_validator(mode="after")
    def _derive_celery_broker_url(self) -> "Settings":
        """Default broker_url to redis.url when not explicitly set."""
        if self.celery.broker_url is None:
            self.celery.broker_url = self.redis.url
        return self

    model_config = SettingsConfigDict(
        env_prefix="GIDEON_",
        env_file=".env",
        env_file_encoding="utf-8",
        json_file="config.json",
        json_file_encoding="utf-8",
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
