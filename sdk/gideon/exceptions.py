"""SDK exception hierarchy — maps HTTP status codes to typed errors."""


class GideonError(Exception):
    """Base exception for all Gideon SDK errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class AuthenticationError(GideonError):
    """Raised on HTTP 401 — invalid or expired credentials."""


class AuthorizationError(GideonError):
    """Raised on HTTP 403 — insufficient permissions."""


class NotFoundError(GideonError):
    """Raised on HTTP 404 — resource not found."""


class ValidationError(GideonError):
    """Raised on HTTP 422 — request validation failed."""


class ServerError(GideonError):
    """Raised on HTTP 5xx — server-side error."""
