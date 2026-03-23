"""Base response models shared across all endpoints."""

from pydantic import BaseModel


class MessageResponse(BaseModel):
    detail: str
