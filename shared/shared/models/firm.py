"""Pydantic response models for firm endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class FirmResponse(BaseModel):
    id: UUID
    name: str
    created_at: datetime
