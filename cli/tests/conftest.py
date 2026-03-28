"""Shared test fixtures for the CLI test suite."""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
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
    IngestionConfigResponse,
)
from shared.models.enums import TaskState
from shared.models.firm import FirmResponse
from shared.models.health import HealthResponse, ReadinessResponse, ServiceChecks
from shared.models.matter import MatterResponse, MatterSummary
from shared.models.matter_access import MatterAccessResponse
from shared.models.task import TaskResponse, TaskSubmitResponse, TaskSummary
from shared.models.user import UserResponse, UserSummary
from typer.testing import CliRunner

from opencase_cli import main as main_module


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def app() -> Any:
    return main_module.app


@pytest.fixture()
def tmp_opencase_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect ~/.opencase/ to a temp directory."""
    opencase_dir = tmp_path / ".opencase"
    opencase_dir.mkdir()

    monkeypatch.setattr("opencase_cli.config.opencase_dir", lambda: opencase_dir)
    monkeypatch.setattr("opencase_cli.tokens.opencase_dir", lambda: opencase_dir)
    monkeypatch.setattr(
        "opencase_cli.config.config_path", lambda: opencase_dir / "config.toml"
    )
    return opencase_dir


def make_jwt(
    exp: float | None = None,
    extra: dict[str, object] | None = None,
) -> str:
    """Build a fake JWT with the given exp claim (no real signature)."""
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256"}).encode()).rstrip(
        b"="
    )
    payload: dict[str, object] = {"sub": "user-id"}
    if exp is not None:
        payload["exp"] = exp
    if extra:
        payload.update(extra)
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=")
    sig = base64.urlsafe_b64encode(b"fakesig").rstrip(b"=")
    return f"{header.decode()}.{body.decode()}.{sig.decode()}"


@pytest.fixture()
def stored_tokens(tmp_opencase_dir: Path) -> tuple[str, str]:
    """Write fake tokens to the temp token file and return them."""
    from opencase_cli.tokens import save_tokens

    access = make_jwt(exp=time.time() + 3600)
    refresh = "fake-refresh-token"
    save_tokens(access, refresh)
    return (access, refresh)


@pytest.fixture()
def mock_client() -> MagicMock:
    """Return a MagicMock that quacks like OpenCaseClient."""
    from opencase import OpenCaseClient

    mock = MagicMock(spec=OpenCaseClient)
    mock.__enter__ = MagicMock(return_value=mock)
    mock.__exit__ = MagicMock(return_value=False)
    # Default ingestion config for bulk-ingest tests
    mock.get_ingestion_config.return_value = IngestionConfigResponse(
        allowed_content_types=[
            "application/pdf",
            "text/plain",
        ],
        allowed_extensions=[
            ".pdf",
            ".doc",
            ".docx",
            ".txt",
            ".md",
            ".csv",
            ".html",
            ".htm",
            ".xlsx",
            ".pptx",
            ".rtf",
            ".jpg",
            ".jpeg",
            ".png",
            ".tiff",
            ".tif",
            ".gif",
            ".bmp",
            ".webp",
        ],
    )
    return mock


# -- pre-built response objects -----------------------------------------------


HEALTH_RESPONSE = HealthResponse(status="ok", app="opencase", version="0.1.0")

READINESS_RESPONSE = ReadinessResponse(
    status="ok", services=ServiceChecks(postgres="ok")
)

READINESS_DEGRADED = ReadinessResponse(
    status="degraded", services=ServiceChecks(postgres="error")
)

TOKEN_RESPONSE = TokenResponse(access_token="access-tok", refresh_token="refresh-tok")

MFA_REQUIRED = MfaRequiredResponse(mfa_required=True, mfa_token="mfa-tok")

MFA_SETUP = MfaSetupResponse(
    totp_secret="JBSWY3DPEHPK3PXP",
    provisioning_uri="otpauth://totp/OpenCase:user@firm.com?secret=JBSWY3DPEHPK3PXP",
)

MFA_ENABLED = MfaStatusResponse(enabled=True)
MFA_DISABLED = MfaStatusResponse(enabled=False)

LOGOUT_RESPONSE = MessageResponse(detail="Logged out")

USER_SUMMARY = UserSummary(
    id="00000000-0000-0000-0000-000000000001",
    email="user@firm.com",
    first_name="Jane",
    last_name="Doe",
    role="attorney",
    is_active=True,
)

USER_RESPONSE = UserResponse(
    id="00000000-0000-0000-0000-000000000001",
    email="user@firm.com",
    first_name="Jane",
    last_name="Doe",
    role="attorney",
    is_active=True,
    title=None,
    middle_initial=None,
    totp_enabled=False,
    firm_id="00000000-0000-0000-0000-000000000002",
    created_at="2025-01-01T00:00:00",
    updated_at="2025-01-01T00:00:00",
)

FIRM_RESPONSE = FirmResponse(
    id="00000000-0000-0000-0000-000000000002",
    name="Cora Firm",
    created_at="2025-01-01T00:00:00",
)

MATTER_SUMMARY = MatterSummary(
    id="00000000-0000-0000-0000-000000000010",
    name="People v. Smith",
    client_id="00000000-0000-0000-0000-000000000020",
    status="open",
    legal_hold=False,
)

MATTER_RESPONSE = MatterResponse(
    id="00000000-0000-0000-0000-000000000010",
    name="People v. Smith",
    client_id="00000000-0000-0000-0000-000000000020",
    status="open",
    legal_hold=False,
    firm_id="00000000-0000-0000-0000-000000000002",
    created_at="2025-01-01T00:00:00",
    updated_at="2025-01-01T00:00:00",
)

MATTER_ACCESS = MatterAccessResponse(
    user_id="00000000-0000-0000-0000-000000000001",
    matter_id="00000000-0000-0000-0000-000000000010",
    view_work_product=False,
    assigned_at="2025-01-01T00:00:00",
)

REVOKE_RESPONSE = MessageResponse(detail="Access revoked")

TASK_SUMMARY = TaskSummary(
    id="00000000-0000-0000-0000-000000000030",
    task_name="ping",
    status=TaskState.pending,
    submitted_at="2025-01-01T00:00:00",
    submitted_by="00000000-0000-0000-0000-000000000001",
)

TASK_RESPONSE = TaskResponse(
    id="00000000-0000-0000-0000-000000000030",
    task_name="ping",
    status=TaskState.success,
    submitted_at="2025-01-01T00:00:00",
    submitted_by="00000000-0000-0000-0000-000000000001",
    firm_id="00000000-0000-0000-0000-000000000002",
    args=[],
    kwargs={},
    result="pong",
    date_done="2025-01-01T00:00:01",
    traceback=None,
)

TASK_SUBMIT_RESPONSE = TaskSubmitResponse(
    task_id="00000000-0000-0000-0000-000000000030",
)

TASK_CANCEL_RESPONSE = MessageResponse(detail="Task revoked")

DOCUMENT_SUMMARY = DocumentSummary(
    id="00000000-0000-0000-0000-000000000040",
    filename="evidence.pdf",
    content_type="application/pdf",
    size_bytes=12345,
    source="defense",
    classification="unclassified",
    legal_hold=False,
    matter_id="00000000-0000-0000-0000-000000000010",
)

DOCUMENT_RESPONSE = DocumentResponse(
    id="00000000-0000-0000-0000-000000000040",
    firm_id="00000000-0000-0000-0000-000000000002",
    matter_id="00000000-0000-0000-0000-000000000010",
    filename="evidence.pdf",
    content_type="application/pdf",
    size_bytes=12345,
    source="defense",
    classification="unclassified",
    legal_hold=False,
    file_hash="a" * 64,
    bates_number=None,
    uploaded_by="00000000-0000-0000-0000-000000000001",
    created_at="2025-01-01T00:00:00",
    updated_at="2025-01-01T00:00:00",
)
