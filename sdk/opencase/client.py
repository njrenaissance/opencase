"""OpenCaseClient — synchronous REST client for the OpenCase API."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any

import httpx
from shared.models.auth import (
    MfaRequiredResponse,
    MfaSetupResponse,
    MfaStatusResponse,
    TokenResponse,
)
from shared.models.base import MessageResponse
from shared.models.document import (
    DocumentResponse,
    DocumentSummary,
    DuplicateCheckResponse,
    IngestionConfigResponse,
)
from shared.models.enums import Classification, DocumentSource, TaskState
from shared.models.firm import FirmResponse
from shared.models.health import HealthResponse, ReadinessResponse
from shared.models.matter import (
    MatterResponse,
    MatterSummary,
)
from shared.models.matter_access import (
    MatterAccessResponse,
)
from shared.models.prompt import (
    PromptResponse,
    PromptSummary,
)
from shared.models.task import (
    TaskResponse,
    TaskSubmitResponse,
    TaskSummary,
)
from shared.models.user import (
    UserResponse,
    UserSummary,
)

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
        resp = self._request("POST", "/auth/mfa/confirm", json={"totp_code": totp_code})
        return MfaStatusResponse.model_validate(resp.json())

    def mfa_disable(self, totp_code: str) -> MfaStatusResponse:
        resp = self._request("POST", "/auth/mfa/disable", json={"totp_code": totp_code})
        return MfaStatusResponse.model_validate(resp.json())

    def logout(self, refresh_token: str | None = None) -> MessageResponse:
        token = refresh_token or self._auth.refresh_token
        resp = self._request("POST", "/auth/logout", json={"refresh_token": token})
        self._auth.clear()
        return MessageResponse.model_validate(resp.json())

    # -- firms ---------------------------------------------------------------

    def get_firm(self) -> FirmResponse:
        resp = self._request("GET", "/firms/me")
        return FirmResponse.model_validate(resp.json())

    # -- users ---------------------------------------------------------------

    def get_current_user(self) -> UserResponse:
        resp = self._request("GET", "/users/me")
        return UserResponse.model_validate(resp.json())

    def list_users(self) -> list[UserSummary]:
        resp = self._request("GET", "/users/")
        return [UserSummary.model_validate(item) for item in resp.json()]

    def get_user(self, user_id: str) -> UserResponse:
        resp = self._request("GET", f"/users/{user_id}")
        return UserResponse.model_validate(resp.json())

    def create_user(
        self,
        *,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        role: str,
        title: str | None = None,
        middle_initial: str | None = None,
    ) -> UserResponse:
        payload: dict[str, Any] = {
            "email": email,
            "password": password,
            "first_name": first_name,
            "last_name": last_name,
            "role": role,
        }
        if title is not None:
            payload["title"] = title
        if middle_initial is not None:
            payload["middle_initial"] = middle_initial
        resp = self._request("POST", "/users/", json=payload)
        return UserResponse.model_validate(resp.json())

    def update_user(self, user_id: str, **kwargs: Any) -> UserResponse:
        resp = self._request("PATCH", f"/users/{user_id}", json=kwargs)
        return UserResponse.model_validate(resp.json())

    # -- matters -------------------------------------------------------------

    def list_matters(self) -> list[MatterSummary]:
        resp = self._request("GET", "/matters/")
        return [MatterSummary.model_validate(item) for item in resp.json()]

    def get_matter(self, matter_id: str) -> MatterResponse:
        resp = self._request("GET", f"/matters/{matter_id}")
        return MatterResponse.model_validate(resp.json())

    def create_matter(
        self,
        *,
        name: str,
        client_id: str,
    ) -> MatterResponse:
        resp = self._request(
            "POST", "/matters/", json={"name": name, "client_id": client_id}
        )
        return MatterResponse.model_validate(resp.json())

    def update_matter(self, matter_id: str, **kwargs: Any) -> MatterResponse:
        resp = self._request("PATCH", f"/matters/{matter_id}", json=kwargs)
        return MatterResponse.model_validate(resp.json())

    # -- matter access -------------------------------------------------------

    def list_matter_access(self, matter_id: str) -> list[MatterAccessResponse]:
        resp = self._request("GET", f"/matters/{matter_id}/access")
        return [MatterAccessResponse.model_validate(item) for item in resp.json()]

    def grant_matter_access(
        self,
        matter_id: str,
        *,
        user_id: str,
        view_work_product: bool = False,
    ) -> MatterAccessResponse:
        resp = self._request(
            "POST",
            f"/matters/{matter_id}/access",
            json={"user_id": user_id, "view_work_product": view_work_product},
        )
        return MatterAccessResponse.model_validate(resp.json())

    def revoke_matter_access(self, matter_id: str, user_id: str) -> MessageResponse:
        resp = self._request("DELETE", f"/matters/{matter_id}/access/{user_id}")
        return MessageResponse.model_validate(resp.json())

    # -- documents -----------------------------------------------------------

    def list_documents(self) -> list[DocumentSummary]:
        resp = self._request("GET", "/documents/")
        return [DocumentSummary.model_validate(item) for item in resp.json()]

    def get_document(self, document_id: str) -> DocumentResponse:
        resp = self._request("GET", f"/documents/{document_id}")
        return DocumentResponse.model_validate(resp.json())

    def get_ingestion_config(self) -> IngestionConfigResponse:
        """Return allowed content types and file extensions for ingestion."""
        resp = self._request("GET", "/documents/ingestion-config")
        return IngestionConfigResponse.model_validate(resp.json())

    def upload_document(
        self,
        *,
        file_path: str | Path,
        matter_id: str,
        source: str = DocumentSource.defense,
        classification: str = Classification.unclassified,
        bates_number: str | None = None,
    ) -> DocumentResponse:
        """Upload a local file to a matter via multipart form data."""
        path = Path(file_path)
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"

        data: dict[str, str] = {
            "matter_id": matter_id,
            "source": source,
            "classification": classification,
        }
        if bates_number is not None:
            data["bates_number"] = bates_number

        with open(path, "rb") as fh:
            files = {"file": (path.name, fh, content_type)}
            resp = self._request("POST", "/documents/", files=files, data=data)
        return DocumentResponse.model_validate(resp.json())

    def check_duplicate(
        self,
        *,
        matter_id: str,
        file_hash: str,
    ) -> DuplicateCheckResponse:
        """Check if a file hash already exists in a matter."""
        resp = self._request(
            "GET",
            "/documents/check-duplicate",
            params={"matter_id": matter_id, "file_hash": file_hash},
        )
        return DuplicateCheckResponse.model_validate(resp.json())

    # -- prompts -------------------------------------------------------------

    def list_prompts(self) -> list[PromptSummary]:
        resp = self._request("GET", "/prompts/")
        return [PromptSummary.model_validate(item) for item in resp.json()]

    def get_prompt(self, prompt_id: str) -> PromptResponse:
        resp = self._request("GET", f"/prompts/{prompt_id}")
        return PromptResponse.model_validate(resp.json())

    def submit_prompt(self, *, matter_id: str, query: str) -> PromptResponse:
        resp = self._request(
            "POST", "/prompts/", json={"matter_id": matter_id, "query": query}
        )
        return PromptResponse.model_validate(resp.json())

    # -- tasks ---------------------------------------------------------------

    def list_tasks(
        self,
        *,
        status: TaskState | None = None,
        task_name: str | None = None,
    ) -> list[TaskSummary]:
        params: dict[str, str] = {}
        if status is not None:
            params["status"] = status
        if task_name is not None:
            params["task_name"] = task_name
        resp = self._request("GET", "/tasks/", params=params)
        return [TaskSummary.model_validate(item) for item in resp.json()]

    def get_task(self, task_id: str) -> TaskResponse:
        resp = self._request("GET", f"/tasks/{task_id}")
        return TaskResponse.model_validate(resp.json())

    def submit_task(
        self,
        *,
        task_name: str,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> TaskSubmitResponse:
        payload: dict[str, Any] = {"task_name": task_name}
        if args is not None:
            payload["args"] = args
        if kwargs is not None:
            payload["kwargs"] = kwargs
        resp = self._request("POST", "/tasks/", json=payload)
        return TaskSubmitResponse.model_validate(resp.json())

    def cancel_task(self, task_id: str) -> MessageResponse:
        resp = self._request("DELETE", f"/tasks/{task_id}")
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
