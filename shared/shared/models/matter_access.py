"""Pydantic request/response models for matter access endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class MatterAccessResponse(BaseModel):
    user_id: UUID
    matter_id: UUID
    view_work_product: bool
    assigned_at: datetime


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class GrantAccessRequest(BaseModel):
    user_id: UUID
    view_work_product: bool = False


class RevokeAccessRequest(BaseModel):
    user_id: UUID
