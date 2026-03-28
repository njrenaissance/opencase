"""Context manager for automatic login/logout lifecycle."""

from __future__ import annotations

from shared.models.auth import MfaRequiredResponse

from opencase.client import Client
from opencase.exceptions import AuthenticationError


class Session:
    """Context manager that logs in on entry and logs out on exit.

    Usage::

        with Session("http://localhost:8000", email="u@f.com", password="s") as client:
            matters = client.list_matters()

    Credentials are scrubbed from the instance immediately after login.
    If the server requires MFA, ``AuthenticationError`` is raised — use
    ``Client`` directly for interactive MFA flows.
    """

    def __init__(
        self,
        base_url: str,
        *,
        email: str,
        password: str,
        timeout: float = 30.0,
    ) -> None:
        self._client = Client(base_url=base_url, timeout=timeout)
        self._email: str | None = email
        self._password: str | None = password

    @property
    def client(self) -> Client:
        return self._client

    def __enter__(self) -> Client:
        try:
            result = self._client.login(self._email, self._password)  # type: ignore[arg-type]
        finally:
            # Scrub credentials regardless of success/failure.
            self._email = None
            self._password = None
        if isinstance(result, MfaRequiredResponse):
            self._client.close()
            raise AuthenticationError(
                "MFA required — use Client directly for interactive MFA",
                status_code=None,
            )
        return self._client

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        try:
            if self._client._auth.is_authenticated:  # noqa: SLF001
                self._client.logout()
        finally:
            self._client.close()

    async def __aenter__(self) -> Client:
        raise NotImplementedError("Async not supported — the SDK client is synchronous")

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        raise NotImplementedError("Async not supported — the SDK client is synchronous")
