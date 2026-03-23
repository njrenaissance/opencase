"""OpenCaseClient — synchronous REST client for the OpenCase API."""

from __future__ import annotations

from typing import Any

import httpx
from shared.models.auth import (
    MfaRequiredResponse,
    MfaSetupResponse,
    MfaStatusResponse,
    TokenResponse,
)
from shared.models.base import MessageResponse
from shared.models.health import HealthResponse, ReadinessResponse

from opencase._auth import AuthManager
from opencase.exceptions import (
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    OpenCaseError,
    ServerError,
    ValidationError,
)


class OpenCaseClient:
    """Synchronous Python client for the OpenCase REST API.

    Handles JWT lifecycle transparently: auto-refreshes expired access
    tokens before requests and retries once on 401.

    Usage::

        client = OpenCaseClient(base_url="http://localhost:8000")
        client.login(email="user@firm.com", password="secret")

        health = client.health()
        client.logout()

    Or as a context manager::

        with OpenCaseClient(base_url="http://localhost:8000") as client:
            client.login(email="user@firm.com", password="secret")
            ...
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._http = httpx.Client(timeout=timeout)
        self._auth = AuthManager()

    # -- context manager -----------------------------------------------------

    def __enter__(self) -> OpenCaseClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._http.close()

    # -- health (unauthenticated) --------------------------------------------

    def health(self) -> HealthResponse:
        resp = self._request("GET", "/health", authenticated=False)
        return HealthResponse.model_validate(resp.json())

    def readiness(self) -> ReadinessResponse:
        resp = self._request("GET", "/ready", authenticated=False)
        return ReadinessResponse.model_validate(resp.json())

    # -- auth ----------------------------------------------------------------

    def login(
        self,
        email: str,
        password: str,
    ) -> TokenResponse | MfaRequiredResponse:
        """Authenticate with email and password.

        Returns ``TokenResponse`` on success (tokens stored internally)
        or ``MfaRequiredResponse`` when MFA verification is required
        (call ``verify_mfa`` next).
        """
        resp = self._request(
            "POST",
            "/auth/login",
            json={"email": email, "password": password},
            authenticated=False,
        )
        data = resp.json()
        if data.get("mfa_required"):
            return MfaRequiredResponse.model_validate(data)
        result = TokenResponse.model_validate(data)
        self._auth.store_tokens(result.access_token, result.refresh_token)
        return result

    def verify_mfa(self, mfa_token: str, totp_code: str) -> TokenResponse:
        """Complete MFA verification after login returns ``MfaRequiredResponse``."""
        resp = self._request(
            "POST",
            "/auth/mfa/verify",
            json={"mfa_token": mfa_token, "totp_code": totp_code},
            authenticated=False,
        )
        result = TokenResponse.model_validate(resp.json())
        self._auth.store_tokens(result.access_token, result.refresh_token)
        return result

    def mfa_setup(self) -> MfaSetupResponse:
        resp = self._request("POST", "/auth/mfa/setup")
        return MfaSetupResponse.model_validate(resp.json())

    def mfa_confirm(self, totp_code: str) -> MfaStatusResponse:
        resp = self._request(
            "POST", "/auth/mfa/confirm", json={"totp_code": totp_code}
        )
        return MfaStatusResponse.model_validate(resp.json())

    def mfa_disable(self, totp_code: str) -> MfaStatusResponse:
        resp = self._request(
            "POST", "/auth/mfa/disable", json={"totp_code": totp_code}
        )
        return MfaStatusResponse.model_validate(resp.json())

    def logout(self, refresh_token: str | None = None) -> MessageResponse:
        resp = self._request(
            "POST", "/auth/logout", json={"refresh_token": refresh_token}
        )
        self._auth.clear()
        return MessageResponse.model_validate(resp.json())

    # -- internal transport --------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        authenticated: bool = True,
        _retried: bool = False,
        **kwargs: Any,
    ) -> httpx.Response:
        """Central dispatch — injects auth header and handles auto-refresh.

        On 401, attempts one token refresh and retries the original
        request.  Maps HTTP error codes to SDK exceptions.
        """
        headers: dict[str, str] = dict(kwargs.pop("headers", {}) or {})

        if authenticated and self._auth.is_authenticated:
            # Pre-emptive refresh if token is about to expire.
            if self._auth.access_token_expired:
                self._auth.refresh(self._http, self._base_url)
            headers.update(self._auth.authorization_header)

        url = f"{self._base_url}{path}"
        resp = self._http.request(method, url, headers=headers, **kwargs)

        # Auto-refresh on 401 (token may have been revoked server-side).
        if (
            resp.status_code == 401  # noqa: PLR2004
            and authenticated
            and self._auth.is_authenticated
            and not _retried
        ):
            try:
                self._auth.refresh(self._http, self._base_url)
            except AuthenticationError:
                self._raise_for_status(resp)
            return self._request(
                method, path, authenticated=authenticated, _retried=True, **kwargs
            )

        self._raise_for_status(resp)
        return resp

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        """Map HTTP error status codes to SDK exceptions."""
        if resp.is_success:
            return

        detail = ""
        try:
            detail = resp.json().get("detail", "")
        except Exception:  # noqa: BLE001
            detail = resp.text

        code = resp.status_code
        if code == 401:  # noqa: PLR2004
            raise AuthenticationError(detail, status_code=code)
        if code == 403:  # noqa: PLR2004
            raise AuthorizationError(detail, status_code=code)
        if code == 404:  # noqa: PLR2004
            raise NotFoundError(detail, status_code=code)
        if code == 422:  # noqa: PLR2004
            raise ValidationError(detail, status_code=code)
        if code >= 500:  # noqa: PLR2004
            raise ServerError(detail, status_code=code)
        raise OpenCaseError(detail, status_code=code)
