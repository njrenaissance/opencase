"""System matter constants and helpers.

System matters use a reserved UUID range (00000000-0000-0000-0000-0000000000xx)
to distinguish them from real client matters in logs, queries, and API responses.
"""

from __future__ import annotations

import uuid

GLOBAL_KNOWLEDGE_MATTER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
GLOBAL_KNOWLEDGE_MATTER_NAME = "Global Knowledge"

# Sentinel client_id for system matters — not a real client.
SYSTEM_CLIENT_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")

# All system matter UUIDs share this prefix.
SYSTEM_MATTER_PREFIX = "00000000-0000-0000-0000-"


def is_system_matter(matter_id: uuid.UUID) -> bool:
    """Return True if the matter_id falls in the reserved system range."""
    return str(matter_id).startswith(SYSTEM_MATTER_PREFIX)
