"""System matter constants and helpers.

System matters use reserved UUIDs from a closed set to distinguish them
from real client matters in logs, queries, and API responses.
"""

from __future__ import annotations

import uuid

GLOBAL_KNOWLEDGE_MATTER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
GLOBAL_KNOWLEDGE_MATTER_NAME = "Global Knowledge"

# Sentinel client_id for system matters — not a real client.
SYSTEM_CLIENT_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")

# Closed set of all system matter UUIDs.  Add new system matters here.
_SYSTEM_MATTERS: frozenset[uuid.UUID] = frozenset(
    {
        GLOBAL_KNOWLEDGE_MATTER_ID,
    }
)


def is_system_matter(matter_id: uuid.UUID) -> bool:
    """Return True if the matter_id is a known system matter."""
    return matter_id in _SYSTEM_MATTERS
