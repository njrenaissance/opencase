"""Gideon Python SDK — REST client for the Gideon API."""

from gideon.client import Client
from gideon.exceptions import (
    AuthenticationError,
    AuthorizationError,
    GideonError,
    NotFoundError,
    ServerError,
    ValidationError,
)
from gideon.session import Session

__version__ = "0.1.0"

# Backwards-compatible alias.
GideonClient = Client

__all__ = [
    "AuthenticationError",
    "AuthorizationError",
    "Client",
    "NotFoundError",
    "GideonClient",
    "GideonError",
    "ServerError",
    "Session",
    "ValidationError",
]
