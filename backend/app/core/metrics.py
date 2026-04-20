"""Module-level OTel metric instruments for authentication events.

Import and call these from the auth router (1.4) to record auth activity.
All instruments are created lazily after setup_telemetry() initializes the
MeterProvider.

Usage::

    from app.core.metrics import login_attempts

    login_attempts.add(1, {"result": "success"})
    login_attempts.add(1, {"result": "failure"})
    login_attempts.add(1, {"result": "locked"})
"""

import threading
from typing import Any

from app.core.telemetry import get_meter

_instruments_cache: dict[str, Any] | None = None
_instruments_lock = threading.Lock()


def _create_instruments() -> None:
    """Create all metric instruments. Called once after setup_telemetry()."""
    global _instruments_cache  # noqa: PLW0603
    if _instruments_cache is not None:
        return

    with _instruments_lock:
        if _instruments_cache is not None:
            return

        meter = get_meter()
        cache: dict[str, Any] = {}

        cache["login_attempts"] = meter.create_counter(
        "gideon.auth.login_attempts",
        description="Login attempts by result",
    )

    cache["mfa_challenges"] = meter.create_counter(
        "gideon.auth.mfa_challenges",
        description="MFA TOTP challenge outcomes",  # attrs: result=(success|failure)
    )

    cache["token_refresh_attempts"] = meter.create_counter(
        "gideon.auth.token_refresh_attempts",
        description="Token refresh attempts",
    )

    cache["active_sessions"] = meter.create_up_down_counter(
        "gideon.auth.active_sessions",
        description="Currently active sessions (access tokens issued minus logouts)",
    )

    cache["access_denied"] = meter.create_counter(
        "gideon.rbac.access_denied",
        description="RBAC access denials",  # attrs: reason=(role|matter), role=<role>
    )

    cache["users_created"] = meter.create_counter(
        "gideon.users.created",
        description="Users created",
    )

    cache["users_updated"] = meter.create_counter(
        "gideon.users.updated",
        description="Users updated",
    )

    cache["matters_created"] = meter.create_counter(
        "gideon.matters.created",
        description="Matters created",
    )

    cache["matters_updated"] = meter.create_counter(
        "gideon.matters.updated",
        description="Matters updated",
    )

    cache["matter_access_granted"] = meter.create_counter(
        "gideon.matter_access.granted",
        description="Matter access grants",
    )

    cache["matter_access_revoked"] = meter.create_counter(
        "gideon.matter_access.revoked",
        description="Matter access revocations",
    )

    cache["documents_created"] = meter.create_counter(
        "gideon.documents.created",
        description="Documents created",
    )

    cache["documents_duplicates_rejected"] = meter.create_counter(
        "gideon.documents.duplicates_rejected",
        description="Duplicate document upload rejections",
    )

    cache["prompts_created"] = meter.create_counter(
        "gideon.prompts.created",
        description="Prompts submitted",
    )

    cache["chat_queries_created"] = meter.create_counter(
        "gideon.chat.queries.created",
        description="Chat queries submitted",
    )

    cache["tasks_submitted"] = meter.create_counter(
        "gideon.tasks.submitted",
        description="Tasks submitted via API",
    )

    cache["tasks_cancelled"] = meter.create_counter(
        "gideon.tasks.cancelled",
        description="Tasks cancelled via API",
    )

    cache["tasks_status_queried"] = meter.create_counter(
        "gideon.tasks.status_queried",
        description="Task status queries via broker",
    )

    cache["extraction_completed"] = meter.create_counter(
        "gideon.extraction.completed",
        description="Successful text extractions",  # attrs: content_type, ocr_applied
    )

    cache["extraction_failed"] = meter.create_counter(
        "gideon.extraction.failed",
        description="Failed text extractions",  # attrs: content_type, error_type
    )

    cache["extraction_duration_seconds"] = meter.create_histogram(
        "gideon.extraction.duration_seconds",
        description="Extraction latency in seconds",
        unit="s",
    )

    cache["extraction_document_size_bytes"] = meter.create_histogram(
        "gideon.extraction.document_size_bytes",
        description="Input document size in bytes",
        unit="By",
    )

    cache["extraction_text_length_chars"] = meter.create_histogram(
        "gideon.extraction.text_length_chars",
        description="Extracted text length in characters",
        unit="{char}",
    )

    cache["chunking_completed"] = meter.create_counter(
        "gideon.chunking.completed",
        description="Successful chunk operations",  # attrs: strategy
    )

    cache["chunking_failed"] = meter.create_counter(
        "gideon.chunking.failed",
        description="Failed chunk operations",  # attrs: error_type
    )

    cache["chunking_duration_seconds"] = meter.create_histogram(
        "gideon.chunking.duration_seconds",
        description="Chunking latency in seconds",
        unit="s",
    )

    cache["chunking_text_length_chars"] = meter.create_histogram(
        "gideon.chunking.text_length_chars",
        description="Input text length in characters",
        unit="{char}",
    )

    cache["chunking_chunks_produced"] = meter.create_histogram(
        "gideon.chunking.chunks_produced",
        description="Number of chunks produced per document",
        unit="{chunk}",
    )

    cache["embedding_completed"] = meter.create_counter(
        "gideon.embedding.completed",
        description="Successful embedding operations",  # attrs: model
    )

    cache["embedding_failed"] = meter.create_counter(
        "gideon.embedding.failed",
        description="Failed embedding operations",  # attrs: model, error_type
    )

    cache["embedding_duration_seconds"] = meter.create_histogram(
        "gideon.embedding.duration_seconds",
        description="Embedding latency in seconds",
        unit="s",
    )

    cache["embedding_chunks_processed"] = meter.create_histogram(
        "gideon.embedding.chunks_processed",
        description="Number of chunks embedded per call",
        unit="{chunk}",
    )

    cache["embedding_batch_count"] = meter.create_histogram(
        "gideon.embedding.batch_count",
        description="Number of batches per embedding call",
        unit="{batch}",
    )

    cache["vectorstore_upsert_completed"] = meter.create_counter(
        "gideon.vectorstore.upsert.completed",
        description="Successful vector upsert operations",  # attrs: collection
    )

    cache["vectorstore_upsert_failed"] = meter.create_counter(
        "gideon.vectorstore.upsert.failed",
        description="Failed vector upsert operations",  # attrs: collection, error_type
    )

    cache["vectorstore_upsert_duration_seconds"] = meter.create_histogram(
        "gideon.vectorstore.upsert.duration_seconds",
        description="Vector upsert latency in seconds",
        unit="s",
    )

    cache["vectorstore_upsert_points"] = meter.create_histogram(
        "gideon.vectorstore.upsert.points",
        description="Number of points upserted per call",
        unit="{point}",
    )

    cache["vectorstore_delete_completed"] = meter.create_counter(
        "gideon.vectorstore.delete.completed",
        description="Successful vector delete operations",  # attrs: collection
    )

    cache["vectorstore_delete_failed"] = meter.create_counter(
        "gideon.vectorstore.delete.failed",
        description="Failed vector delete operations",  # attrs: collection, error_type
    )

    cache["vectorstore_delete_duration_seconds"] = meter.create_histogram(
        "gideon.vectorstore.delete.duration_seconds",
        description="Vector delete latency in seconds",
        unit="s",
    )

    cache["vectorstore_search_completed"] = meter.create_counter(
        "gideon.vectorstore.search.completed",
        description="Successful vector similarity search operations",
    )

    cache["vectorstore_search_failed"] = meter.create_counter(
        "gideon.vectorstore.search.failed",
        description="Failed vector similarity search operations",  # attrs: collection
    )

    cache["vectorstore_search_duration_seconds"] = meter.create_histogram(
        "gideon.vectorstore.search.duration_seconds",
        description="Vector search latency in seconds",
        unit="s",
    )

    _instruments_cache = cache


class _LazyInstrument:
    """Wrapper that defers instrument access until after setup_telemetry()."""

    def __init__(self, name: str) -> None:
        self._name = name

    def _get_real(self) -> Any:
        _create_instruments()
        if _instruments_cache is None:
            msg = "Instruments were not created by setup_telemetry()"
            raise RuntimeError(msg)
        if self._name not in _instruments_cache:
            msg = f"Instrument '{self._name}' not found in cache"
            raise RuntimeError(msg)
        return _instruments_cache[self._name]

    def __getattr__(self, attr: str) -> Any:
        return getattr(self._get_real(), attr)

    def __repr__(self) -> str:
        return f"_LazyInstrument({self._name!r})"


login_attempts = _LazyInstrument("login_attempts")
mfa_challenges = _LazyInstrument("mfa_challenges")
token_refresh_attempts = _LazyInstrument("token_refresh_attempts")
active_sessions = _LazyInstrument("active_sessions")
access_denied = _LazyInstrument("access_denied")
users_created = _LazyInstrument("users_created")
users_updated = _LazyInstrument("users_updated")
matters_created = _LazyInstrument("matters_created")
matters_updated = _LazyInstrument("matters_updated")
matter_access_granted = _LazyInstrument("matter_access_granted")
matter_access_revoked = _LazyInstrument("matter_access_revoked")
documents_created = _LazyInstrument("documents_created")
documents_duplicates_rejected = _LazyInstrument("documents_duplicates_rejected")
prompts_created = _LazyInstrument("prompts_created")
chat_queries_created = _LazyInstrument("chat_queries_created")
tasks_submitted = _LazyInstrument("tasks_submitted")
tasks_cancelled = _LazyInstrument("tasks_cancelled")
tasks_status_queried = _LazyInstrument("tasks_status_queried")
extraction_completed = _LazyInstrument("extraction_completed")
extraction_failed = _LazyInstrument("extraction_failed")
extraction_duration_seconds = _LazyInstrument("extraction_duration_seconds")
extraction_document_size_bytes = _LazyInstrument("extraction_document_size_bytes")
extraction_text_length_chars = _LazyInstrument("extraction_text_length_chars")
chunking_completed = _LazyInstrument("chunking_completed")
chunking_failed = _LazyInstrument("chunking_failed")
chunking_duration_seconds = _LazyInstrument("chunking_duration_seconds")
chunking_text_length_chars = _LazyInstrument("chunking_text_length_chars")
chunking_chunks_produced = _LazyInstrument("chunking_chunks_produced")
embedding_completed = _LazyInstrument("embedding_completed")
embedding_failed = _LazyInstrument("embedding_failed")
embedding_duration_seconds = _LazyInstrument("embedding_duration_seconds")
embedding_chunks_processed = _LazyInstrument("embedding_chunks_processed")
embedding_batch_count = _LazyInstrument("embedding_batch_count")
vectorstore_upsert_completed = _LazyInstrument(
    "vectorstore_upsert_completed"
)
vectorstore_upsert_failed = _LazyInstrument(
    "vectorstore_upsert_failed"
)
vectorstore_upsert_duration_seconds = _LazyInstrument(
    "vectorstore_upsert_duration_seconds"
)
vectorstore_upsert_points = _LazyInstrument("vectorstore_upsert_points")
vectorstore_delete_completed = _LazyInstrument(
    "vectorstore_delete_completed"
)
vectorstore_delete_failed = _LazyInstrument(
    "vectorstore_delete_failed"
)
vectorstore_delete_duration_seconds = _LazyInstrument(
    "vectorstore_delete_duration_seconds"
)
vectorstore_search_completed = _LazyInstrument(
    "vectorstore_search_completed"
)
vectorstore_search_failed = _LazyInstrument(
    "vectorstore_search_failed"
)
vectorstore_search_duration_seconds = _LazyInstrument(
    "vectorstore_search_duration_seconds"
)
