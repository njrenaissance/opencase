"""Unit tests for shared Pydantic models — validation, serialization, rejection."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from shared.models.enums import MatterStatus, Role
from shared.models.firm import FirmResponse
from shared.models.matter import (
    CreateMatterRequest,
    MatterResponse,
    MatterSummary,
    UpdateMatterRequest,
)
from shared.models.matter_access import (
    GrantAccessRequest,
    MatterAccessResponse,
    RevokeAccessRequest,
)
from shared.models.user import (
    CreateUserRequest,
    UpdateUserRequest,
    UserResponse,
    UserSummary,
)

# ---------------------------------------------------------------------------
# FirmResponse
# ---------------------------------------------------------------------------


class TestFirmResponse:
    def test_valid(self) -> None:
        firm = FirmResponse(
            id=uuid.uuid4(),
            name="Cora Firm",
            created_at=datetime.now(UTC),
        )
        data = firm.model_dump()
        assert data["name"] == "Cora Firm"

    def test_missing_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FirmResponse(id=uuid.uuid4(), created_at=datetime.now(UTC))  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# UserSummary / UserResponse
# ---------------------------------------------------------------------------


class TestUserSummary:
    def test_valid(self) -> None:
        user = UserSummary(
            id=uuid.uuid4(),
            email="alice@firm.com",
            first_name="Alice",
            last_name="Smith",
            role=Role.attorney,
            is_active=True,
        )
        data = user.model_dump()
        assert data["role"] == "attorney"

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("email", "not-an-email"),
            ("role", "superadmin"),
        ],
    )
    def test_invalid_field_rejected(self, field: str, value: str) -> None:
        kwargs = {
            "id": uuid.uuid4(),
            "email": "alice@firm.com",
            "first_name": "Alice",
            "last_name": "Smith",
            "role": Role.attorney,
            "is_active": True,
            field: value,
        }
        with pytest.raises(ValidationError):
            UserSummary(**kwargs)  # type: ignore[arg-type]


class TestUserResponse:
    def test_valid(self) -> None:
        now = datetime.now(UTC)
        user = UserResponse(
            id=uuid.uuid4(),
            email="alice@firm.com",
            first_name="Alice",
            last_name="Smith",
            role=Role.admin,
            is_active=True,
            title="Partner",
            middle_initial="B",
            totp_enabled=False,
            firm_id=uuid.uuid4(),
            created_at=now,
            updated_at=now,
        )
        data = user.model_dump()
        assert data["title"] == "Partner"
        assert data["totp_enabled"] is False

    def test_optional_fields_default_to_none(self) -> None:
        now = datetime.now(UTC)
        user = UserResponse(
            id=uuid.uuid4(),
            email="alice@firm.com",
            first_name="Alice",
            last_name="Smith",
            role=Role.admin,
            is_active=True,
            title=None,
            middle_initial=None,
            totp_enabled=False,
            firm_id=uuid.uuid4(),
            created_at=now,
            updated_at=now,
        )
        assert user.title is None
        assert user.middle_initial is None


# ---------------------------------------------------------------------------
# CreateUserRequest / UpdateUserRequest
# ---------------------------------------------------------------------------


class TestCreateUserRequest:
    def test_valid(self) -> None:
        req = CreateUserRequest(
            email="new@firm.com",
            password="a-long-password",
            first_name="Bob",
            last_name="Jones",
            role=Role.paralegal,
        )
        assert req.email == "new@firm.com"

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("password", "short"),
            ("email", "bad-email"),
            ("first_name", ""),
        ],
    )
    def test_invalid_field_rejected(self, field: str, value: str) -> None:
        kwargs = {
            "email": "new@firm.com",
            "password": "a-long-password",
            "first_name": "Bob",
            "last_name": "Jones",
            "role": Role.paralegal,
            field: value,
        }
        with pytest.raises(ValidationError):
            CreateUserRequest(**kwargs)

    def test_optional_fields_default_none(self) -> None:
        req = CreateUserRequest(
            email="new@firm.com",
            password="a-long-password",
            first_name="Bob",
            last_name="Jones",
            role=Role.paralegal,
        )
        assert req.title is None
        assert req.middle_initial is None


class TestUpdateUserRequest:
    def test_all_fields_optional(self) -> None:
        req = UpdateUserRequest()
        data = req.model_dump(exclude_unset=True)
        assert data == {}

    def test_partial_update(self) -> None:
        req = UpdateUserRequest(first_name="Updated")
        data = req.model_dump(exclude_unset=True)
        assert data == {"first_name": "Updated"}

    def test_invalid_email_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UpdateUserRequest(email="not-valid")


# ---------------------------------------------------------------------------
# MatterSummary / MatterResponse
# ---------------------------------------------------------------------------


class TestMatterSummary:
    def test_valid(self) -> None:
        matter = MatterSummary(
            id=uuid.uuid4(),
            name="People v. Smith",
            client_id=uuid.uuid4(),
            status=MatterStatus.open,
            legal_hold=False,
        )
        data = matter.model_dump()
        assert data["status"] == "open"

    def test_invalid_status_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MatterSummary(
                id=uuid.uuid4(),
                name="Test",
                client_id=uuid.uuid4(),
                status="invalid",  # type: ignore[arg-type]
                legal_hold=False,
            )


class TestMatterResponse:
    def test_valid(self) -> None:
        now = datetime.now(UTC)
        matter = MatterResponse(
            id=uuid.uuid4(),
            name="People v. Smith",
            client_id=uuid.uuid4(),
            status=MatterStatus.open,
            legal_hold=True,
            firm_id=uuid.uuid4(),
            created_at=now,
            updated_at=now,
        )
        assert matter.legal_hold is True


# ---------------------------------------------------------------------------
# CreateMatterRequest / UpdateMatterRequest
# ---------------------------------------------------------------------------


class TestCreateMatterRequest:
    def test_valid(self) -> None:
        req = CreateMatterRequest(name="New Matter", client_id=uuid.uuid4())
        assert req.name == "New Matter"

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValidationError, match="string_too_short"):
            CreateMatterRequest(name="", client_id=uuid.uuid4())


class TestUpdateMatterRequest:
    def test_all_fields_optional(self) -> None:
        req = UpdateMatterRequest()
        assert req.model_dump(exclude_unset=True) == {}

    def test_partial_update(self) -> None:
        req = UpdateMatterRequest(status=MatterStatus.closed)
        data = req.model_dump(exclude_unset=True)
        assert data == {"status": "closed"}


# ---------------------------------------------------------------------------
# MatterAccessResponse / GrantAccessRequest / RevokeAccessRequest
# ---------------------------------------------------------------------------


class TestMatterAccessResponse:
    def test_valid(self) -> None:
        resp = MatterAccessResponse(
            user_id=uuid.uuid4(),
            matter_id=uuid.uuid4(),
            view_work_product=True,
            assigned_at=datetime.now(UTC),
        )
        assert resp.view_work_product is True


class TestGrantAccessRequest:
    def test_valid(self) -> None:
        req = GrantAccessRequest(user_id=uuid.uuid4())
        assert req.view_work_product is False

    def test_with_work_product(self) -> None:
        req = GrantAccessRequest(user_id=uuid.uuid4(), view_work_product=True)
        assert req.view_work_product is True


class TestRevokeAccessRequest:
    def test_valid(self) -> None:
        uid = uuid.uuid4()
        req = RevokeAccessRequest(user_id=uid)
        assert req.user_id == uid
