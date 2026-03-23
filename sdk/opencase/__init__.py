"""OpenCase Python SDK — REST client for the OpenCase API."""

from opencase.client import OpenCaseClient
from opencase.exceptions import (
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    OpenCaseError,
    ServerError,
    ValidationError,
)

__version__ = "0.1.0"

__all__ = [
    "AuthenticationError",
    "AuthorizationError",
    "NotFoundError",
    "OpenCaseClient",
    "OpenCaseError",
    "ServerError",
    "ValidationError",
]
