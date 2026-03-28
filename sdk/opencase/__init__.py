"""OpenCase Python SDK — REST client for the OpenCase API."""

from opencase.client import Client
from opencase.exceptions import (
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    OpenCaseError,
    ServerError,
    ValidationError,
)
from opencase.session import Session

__version__ = "0.1.0"

# Backwards-compatible alias.
OpenCaseClient = Client

__all__ = [
    "AuthenticationError",
    "AuthorizationError",
    "Client",
    "NotFoundError",
    "OpenCaseClient",
    "OpenCaseError",
    "ServerError",
    "Session",
    "ValidationError",
]
