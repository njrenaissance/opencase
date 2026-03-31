"""Vector store models — Qdrant point payload and ID generation."""

from __future__ import annotations

import uuid
from typing import TypedDict

# Fixed namespace for deterministic point IDs via uuid5.
# NEVER change this value — doing so would create duplicate points on
# re-ingestion instead of overwriting existing ones.
POINT_ID_NAMESPACE = uuid.UUID("b6e7f2a1-4c3d-4e8f-9a1b-2d3e4f5a6b7c")


class VectorPayload(TypedDict):
    """Qdrant point payload matching the permission metadata contract.

    Every vector stored in Qdrant must carry these fields so that
    ``build_qdrant_filter()`` can enforce RBAC on every query.
    """

    firm_id: str
    matter_id: str
    client_id: str
    document_id: str
    chunk_index: int
    classification: str
    source: str
    bates_number: str | None
    page_number: int | None


# Keys that must be present in payload_metadata passed to the task.
# document_id and chunk_index are set per-chunk, not from metadata.
REQUIRED_METADATA_KEYS: frozenset[str] = frozenset(
    {
        "firm_id",
        "matter_id",
        "client_id",
        "classification",
        "source",
    }
)


def make_point_id(document_id: str, chunk_index: int) -> str:
    """Generate a deterministic UUID string for a Qdrant point.

    Uses UUID5 so that re-ingesting the same document overwrites
    existing points rather than creating duplicates.
    """
    return str(uuid.uuid5(POINT_ID_NAMESPACE, f"{document_id}:{chunk_index}"))
