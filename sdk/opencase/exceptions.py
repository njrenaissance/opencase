"""SDK exception hierarchy — maps HTTP status codes to typed errors."""


class OpenCaseError(Exception):
    """Base exception for all OpenCase SDK errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class AuthenticationError(OpenCaseError):
    """Raised on HTTP 401 — invalid or expired credentials."""


class AuthorizationError(OpenCaseError):
    """Raised on HTTP 403 — insufficient permissions."""


class NotFoundError(OpenCaseError):
    """Raised on HTTP 404 — resource not found."""


class ValidationError(OpenCaseError):
    """Raised on HTTP 422 — request validation failed."""


class ServerError(OpenCaseError):
    """Raised on HTTP 5xx — server-side error."""
