"""Internal token manager — handles JWT storage and auto-refresh."""

from __future__ import annotations

import base64
import json
import threading
import time

import httpx

from gideon.exceptions import AuthenticationError


class AuthManager:
    """Manages access and refresh tokens for the SDK client.

    The manager peeks at the JWT ``exp`` claim (without signature
    verification) to avoid unnecessary 401 round-trips.  The server
    remains the authority on token validity.

    All token mutations are guarded by a lock so the manager is safe
    to share across threads.
    """

    _EXPIRY_BUFFER_SECONDS = 30

    def __init__(self) -> None:
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._lock = threading.Lock()

    # -- public properties ---------------------------------------------------

    @property
    def is_authenticated(self) -> bool:
        return self._access_token is not None

    @property
    def access_token(self) -> str | None:
        return self._access_token

    @property
    def refresh_token(self) -> str | None:
        return self._refresh_token

    @property
    def access_token_expired(self) -> bool:
        """Return True if the access token's ``exp`` claim is in the past."""
        if self._access_token is None:
            return True
        exp = self._peek_exp(self._access_token)
        if exp is None:
            return True
        return time.time() >= (exp - self._EXPIRY_BUFFER_SECONDS)

    @property
    def authorization_header(self) -> dict[str, str]:
        if self._access_token is None:
            return {}
        return {"Authorization": f"Bearer {self._access_token}"}

    # -- mutations -----------------------------------------------------------

    def store_tokens(self, access_token: str, refresh_token: str) -> None:
        with self._lock:
            self._access_token = access_token
            self._refresh_token = refresh_token

    def clear(self) -> None:
        with self._lock:
            self._access_token = None
            self._refresh_token = None

    def refresh(self, http: httpx.Client, base_url: str) -> None:
        """Call ``POST /auth/refresh`` and store the new token pair.

        Uses double-checked locking: if another thread already refreshed
        while we waited for the lock, skip the network call.

        Raises ``AuthenticationError`` if the refresh fails.
        """
        with self._lock:
            # Double-check: another thread may have refreshed while we waited.
            if not self.access_token_expired:
                return

            if self._refresh_token is None:
                msg = "No refresh token available"
                raise AuthenticationError(msg, status_code=401)

            resp = http.post(
                f"{base_url}/auth/refresh",
                json={"refresh_token": self._refresh_token},
            )
            if resp.status_code != 200:  # noqa: PLR2004
                self._access_token = None
                self._refresh_token = None
                msg = "Token refresh failed"
                raise AuthenticationError(msg, status_code=resp.status_code)

            data = resp.json()
            self._access_token = data["access_token"]
            self._refresh_token = data["refresh_token"]

    # -- internal helpers ----------------------------------------------------

    @staticmethod
    def _peek_exp(token: str) -> float | None:
        """Decode the JWT payload to read the ``exp`` claim.

        This does **not** verify the signature — the server is the
        authority.  We only need ``exp`` as a hint to pre-empt 401s.
        """
        try:
            parts = token.split(".")
            if len(parts) != 3:  # noqa: PLR2004
                return None
            # JWT base64url → standard base64
            payload_b64 = parts[1]
            # Add padding
            padding = 4 - len(payload_b64) % 4
            if padding != 4:  # noqa: PLR2004
                payload_b64 += "=" * padding
            payload_bytes = base64.urlsafe_b64decode(payload_b64)
            payload = json.loads(payload_bytes)
            exp = payload.get("exp")
            return float(exp) if exp is not None else None
        except Exception:  # noqa: BLE001
            return None
