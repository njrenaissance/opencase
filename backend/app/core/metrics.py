"""Module-level OTel metric instruments for authentication events.

Import and call these from the auth router (1.4) to record auth activity.
All instruments are created once at module import time.

Usage::

    from app.core.metrics import login_attempts

    login_attempts.add(1, {"result": "success"})
    login_attempts.add(1, {"result": "failure"})
    login_attempts.add(1, {"result": "locked"})
"""

from app.core.telemetry import meter

login_attempts = meter.create_counter(
    "gideon.auth.login_attempts",
    description="Login attempts by result",  # attrs: result=(success|failure|locked)
)

mfa_challenges = meter.create_counter(
    "gideon.auth.mfa_challenges",
    description="MFA TOTP challenge outcomes",  # attrs: result=(success|failure)
)

token_refresh_attempts = meter.create_counter(
    "gideon.auth.token_refresh_attempts",
    description="Token refresh attempts",
)

active_sessions = meter.create_up_down_counter(
    "gideon.auth.active_sessions",
    description="Currently active sessions (access tokens issued minus logouts)",
)

# ---------------------------------------------------------------------------
# RBAC (Feature 1.5)
# ---------------------------------------------------------------------------

access_denied = meter.create_counter(
    "gideon.rbac.access_denied",
    description="RBAC access denials",  # attrs: reason=(role|matter), role=<role>
)

# ---------------------------------------------------------------------------
# Entity management (Feature 14)
# ---------------------------------------------------------------------------

users_created = meter.create_counter(
    "gideon.users.created",
    description="Users created",
)

users_updated = meter.create_counter(
    "gideon.users.updated",
    description="Users updated",
)

matters_created = meter.create_counter(
    "gideon.matters.created",
    description="Matters created",
)

matters_updated = meter.create_counter(
    "gideon.matters.updated",
    description="Matters updated",
)

matter_access_granted = meter.create_counter(
    "gideon.matter_access.granted",
    description="Matter access grants",
)

matter_access_revoked = meter.create_counter(
    "gideon.matter_access.revoked",
    description="Matter access revocations",
)

# ---------------------------------------------------------------------------
# Documents (Feature 1.8)
# ---------------------------------------------------------------------------

documents_created = meter.create_counter(
    "gideon.documents.created",
    description="Documents created",
)

documents_duplicates_rejected = meter.create_counter(
    "gideon.documents.duplicates_rejected",
    description="Duplicate document upload rejections",
)

# ---------------------------------------------------------------------------
# Prompts (Feature 1.8)
# ---------------------------------------------------------------------------

prompts_created = meter.create_counter(
    "gideon.prompts.created",
    description="Prompts submitted",
)

chat_queries_created = meter.create_counter(
    "gideon.chat.queries.created",
    description="Chat queries submitted",
)

# ---------------------------------------------------------------------------
# Tasks (Feature 2.5–2.6)
# ---------------------------------------------------------------------------

tasks_submitted = meter.create_counter(
    "gideon.tasks.submitted",
    description="Tasks submitted via API",
)

tasks_cancelled = meter.create_counter(
    "gideon.tasks.cancelled",
    description="Tasks cancelled via API",
)

tasks_status_queried = meter.create_counter(
    "gideon.tasks.status_queried",
    description="Task status queries via broker",
)

# ---------------------------------------------------------------------------
# Extraction (Feature 4.4)
# ---------------------------------------------------------------------------

extraction_completed = meter.create_counter(
    "gideon.extraction.completed",
    description="Successful text extractions",  # attrs: content_type, ocr_applied
)

extraction_failed = meter.create_counter(
    "gideon.extraction.failed",
    description="Failed text extractions",  # attrs: content_type, error_type
)

extraction_duration_seconds = meter.create_histogram(
    "gideon.extraction.duration_seconds",
    description="Extraction latency in seconds",
    unit="s",
)

extraction_document_size_bytes = meter.create_histogram(
    "gideon.extraction.document_size_bytes",
    description="Input document size in bytes",
    unit="By",
)

extraction_text_length_chars = meter.create_histogram(
    "gideon.extraction.text_length_chars",
    description="Extracted text length in characters",
    unit="{char}",
)

# ---------------------------------------------------------------------------
# Chunking (Feature 5.6)
# ---------------------------------------------------------------------------

chunking_completed = meter.create_counter(
    "gideon.chunking.completed",
    description="Successful chunk operations",  # attrs: strategy
)

chunking_failed = meter.create_counter(
    "gideon.chunking.failed",
    description="Failed chunk operations",  # attrs: error_type
)

chunking_duration_seconds = meter.create_histogram(
    "gideon.chunking.duration_seconds",
    description="Chunking latency in seconds",
    unit="s",
)

chunking_text_length_chars = meter.create_histogram(
    "gideon.chunking.text_length_chars",
    description="Input text length in characters",
    unit="{char}",
)

chunking_chunks_produced = meter.create_histogram(
    "gideon.chunking.chunks_produced",
    description="Number of chunks produced per document",
    unit="{chunk}",
)

# ---------------------------------------------------------------------------
# Embedding (Feature 5.6)
# ---------------------------------------------------------------------------

embedding_completed = meter.create_counter(
    "gideon.embedding.completed",
    description="Successful embedding operations",  # attrs: model
)

embedding_failed = meter.create_counter(
    "gideon.embedding.failed",
    description="Failed embedding operations",  # attrs: model, error_type
)

embedding_duration_seconds = meter.create_histogram(
    "gideon.embedding.duration_seconds",
    description="Embedding latency in seconds",
    unit="s",
)

embedding_chunks_processed = meter.create_histogram(
    "gideon.embedding.chunks_processed",
    description="Number of chunks embedded per call",
    unit="{chunk}",
)

embedding_batch_count = meter.create_histogram(
    "gideon.embedding.batch_count",
    description="Number of batches per embedding call",
    unit="{batch}",
)

# ---------------------------------------------------------------------------
# Vectorstore (Feature 5.6)
# ---------------------------------------------------------------------------

vectorstore_upsert_completed = meter.create_counter(
    "gideon.vectorstore.upsert.completed",
    description="Successful vector upsert operations",  # attrs: collection
)

vectorstore_upsert_failed = meter.create_counter(
    "gideon.vectorstore.upsert.failed",
    description="Failed vector upsert operations",  # attrs: collection, error_type
)

vectorstore_upsert_duration_seconds = meter.create_histogram(
    "gideon.vectorstore.upsert.duration_seconds",
    description="Vector upsert latency in seconds",
    unit="s",
)

vectorstore_upsert_points = meter.create_histogram(
    "gideon.vectorstore.upsert.points",
    description="Number of points upserted per call",
    unit="{point}",
)

vectorstore_delete_completed = meter.create_counter(
    "gideon.vectorstore.delete.completed",
    description="Successful vector delete operations",  # attrs: collection
)

vectorstore_delete_failed = meter.create_counter(
    "gideon.vectorstore.delete.failed",
    description="Failed vector delete operations",  # attrs: collection, error_type
)

vectorstore_delete_duration_seconds = meter.create_histogram(
    "gideon.vectorstore.delete.duration_seconds",
    description="Vector delete latency in seconds",
    unit="s",
)
