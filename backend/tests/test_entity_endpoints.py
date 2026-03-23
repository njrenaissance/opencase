"""Unit tests for firm, user, matter, and matter_access API endpoints.

Uses AsyncClient + in-memory overrides following the pattern in
test_auth_endpoints.py.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from shared.models.enums import Role

from app.core.auth import create_access_token, get_current_user
from app.db import get_db
from app.db.models.user import User
from app.main import app
from tests.factories import make_firm, make_matter, make_matter_access, make_user

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_FIRM_ID = uuid.uuid4()
_NOW = datetime.now(UTC)


class FakeSession:
    """Async session stand-in with configurable query results."""

    def __init__(self) -> None:
        self._results: list[object] = []
        self._call_idx = 0
        self.committed = False
        self._added: list[object] = []
        self._deleted: list[object] = []

    def add_result(self, obj: object) -> None:
        self._results.append(obj)

    def add_results_list(self, objs: list[object]) -> None:
        self._results.append(objs)

    async def execute(self, stmt: object) -> MagicMock:
        result = MagicMock()
        if self._call_idx < len(self._results):
            val = self._results[self._call_idx]
            self._call_idx += 1
            if isinstance(val, list):
                result.scalars.return_value.all.return_value = val
                result.scalar_one_or_none.return_value = val[0] if val else None
            else:
                result.scalar_one_or_none.return_value = val
                result.scalars.return_value.all.return_value = (
                    [val] if val is not None else []
                )
        else:
            result.scalar_one_or_none.return_value = None
            result.scalars.return_value.all.return_value = []
        return result

    def add(self, obj: object) -> None:
        self._added.append(obj)

    async def delete(self, obj: object) -> None:
        self._deleted.append(obj)

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        pass

    async def refresh(self, obj: object) -> None:
        pass


@asynccontextmanager
async def api_client(user: User, fake: FakeSession) -> AsyncIterator[AsyncClient]:
    """Set up dependency overrides and yield an authenticated AsyncClient."""

    async def _get_db() -> AsyncGenerator[FakeSession, None]:
        yield fake

    async def _get_current_user() -> User:
        return user

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_current_user
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.clear()


def _auth_header(user: User) -> dict[str, str]:
    token = create_access_token(user)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# GET /firms/me
# ---------------------------------------------------------------------------


class TestGetFirm:
    @pytest.mark.asyncio
    async def test_returns_firm(self) -> None:
        firm = make_firm(id=_FIRM_ID, name="Cora Firm", created_at=_NOW)
        user = make_user(firm_id=_FIRM_ID, role=Role.attorney)
        fake = FakeSession()
        fake.add_result(firm)
        async with api_client(user, fake) as ac:
            resp = await ac.get("/firms/me", headers=_auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Cora Firm"


# ---------------------------------------------------------------------------
# GET /users/me
# ---------------------------------------------------------------------------


class TestGetCurrentUser:
    @pytest.mark.asyncio
    async def test_returns_current_user(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()
        async with api_client(user, fake) as ac:
            resp = await ac.get("/users/me", headers=_auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == user.email
        # Sensitive fields must not be present
        assert "hashed_password" not in data
        assert "totp_secret" not in data


# ---------------------------------------------------------------------------
# GET /users/
# ---------------------------------------------------------------------------


class TestListUsers:
    @pytest.mark.asyncio
    async def test_admin_can_list(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        other = make_user(firm_id=_FIRM_ID, role=Role.attorney)
        fake = FakeSession()
        fake.add_results_list([user, other])
        async with api_client(user, fake) as ac:
            resp = await ac.get("/users/", headers=_auth_header(user))
        assert resp.status_code == 200
        assert len(resp.json()) == 2  # noqa: PLR2004

    @pytest.mark.asyncio
    async def test_investigator_forbidden(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.investigator)
        fake = FakeSession()
        async with api_client(user, fake) as ac:
            resp = await ac.get("/users/", headers=_auth_header(user))
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /users/{user_id}
# ---------------------------------------------------------------------------


class TestGetUser:
    @pytest.mark.asyncio
    async def test_returns_user(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        target = make_user(firm_id=_FIRM_ID, role=Role.attorney)
        fake = FakeSession()
        fake.add_result(target)
        async with api_client(user, fake) as ac:
            resp = await ac.get(f"/users/{target.id}", headers=_auth_header(user))
        assert resp.status_code == 200
        assert resp.json()["id"] == str(target.id)

    @pytest.mark.asyncio
    async def test_cross_firm_returns_404(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()
        fake.add_result(None)  # not found in firm
        async with api_client(user, fake) as ac:
            resp = await ac.get(f"/users/{uuid.uuid4()}", headers=_auth_header(user))
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /users/
# ---------------------------------------------------------------------------


class TestCreateUser:
    @pytest.mark.asyncio
    async def test_admin_can_create(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()
        async with api_client(user, fake) as ac:
            resp = await ac.post(
                "/users/",
                json={
                    "email": "new@firm.com",
                    "password": "a-long-password",
                    "first_name": "New",
                    "last_name": "User",
                    "role": "paralegal",
                },
                headers=_auth_header(user),
            )
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_attorney_forbidden(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.attorney)
        fake = FakeSession()
        async with api_client(user, fake) as ac:
            resp = await ac.post(
                "/users/",
                json={
                    "email": "new@firm.com",
                    "password": "a-long-password",
                    "first_name": "New",
                    "last_name": "User",
                    "role": "paralegal",
                },
                headers=_auth_header(user),
            )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# PATCH /users/{user_id}
# ---------------------------------------------------------------------------


class TestUpdateUser:
    @pytest.mark.asyncio
    async def test_admin_can_update(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        target = make_user(firm_id=_FIRM_ID, role=Role.attorney)
        fake = FakeSession()
        fake.add_result(target)
        async with api_client(user, fake) as ac:
            resp = await ac.patch(
                f"/users/{target.id}",
                json={"first_name": "Updated"},
                headers=_auth_header(user),
            )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_self_deactivation_rejected(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()
        fake.add_result(user)  # found self
        async with api_client(user, fake) as ac:
            resp = await ac.patch(
                f"/users/{user.id}",
                json={"is_active": False},
                headers=_auth_header(user),
            )
        assert resp.status_code == 400
        assert "Cannot deactivate your own account" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_update_nonexistent_returns_404(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()
        fake.add_result(None)
        async with api_client(user, fake) as ac:
            resp = await ac.patch(
                f"/users/{uuid.uuid4()}",
                json={"first_name": "Updated"},
                headers=_auth_header(user),
            )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /matters/
# ---------------------------------------------------------------------------


class TestListMatters:
    @pytest.mark.asyncio
    async def test_admin_sees_all(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        m1 = make_matter(firm_id=_FIRM_ID)
        m2 = make_matter(firm_id=_FIRM_ID)
        fake = FakeSession()
        fake.add_results_list([m1, m2])
        async with api_client(user, fake) as ac:
            resp = await ac.get("/matters/", headers=_auth_header(user))
        assert resp.status_code == 200
        assert len(resp.json()) == 2  # noqa: PLR2004


# ---------------------------------------------------------------------------
# GET /matters/{matter_id}
# ---------------------------------------------------------------------------


class TestGetMatter:
    @pytest.mark.asyncio
    async def test_returns_matter(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        matter = make_matter(firm_id=_FIRM_ID)
        fake = FakeSession()
        fake.add_result(matter)
        async with api_client(user, fake) as ac:
            resp = await ac.get(f"/matters/{matter.id}", headers=_auth_header(user))
        assert resp.status_code == 200
        assert resp.json()["name"] == matter.name

    @pytest.mark.asyncio
    async def test_not_found(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()
        fake.add_result(None)
        async with api_client(user, fake) as ac:
            resp = await ac.get(f"/matters/{uuid.uuid4()}", headers=_auth_header(user))
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /matters/
# ---------------------------------------------------------------------------


class TestCreateMatter:
    @pytest.mark.asyncio
    async def test_admin_can_create(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()
        async with api_client(user, fake) as ac:
            resp = await ac.post(
                "/matters/",
                json={"name": "People v. Smith", "client_id": str(uuid.uuid4())},
                headers=_auth_header(user),
            )
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_paralegal_forbidden(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.paralegal)
        fake = FakeSession()
        async with api_client(user, fake) as ac:
            resp = await ac.post(
                "/matters/",
                json={"name": "Test", "client_id": str(uuid.uuid4())},
                headers=_auth_header(user),
            )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# PATCH /matters/{matter_id}
# ---------------------------------------------------------------------------


class TestUpdateMatter:
    @pytest.mark.asyncio
    async def test_admin_can_update(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        matter = make_matter(firm_id=_FIRM_ID)
        fake = FakeSession()
        fake.add_result(matter)
        async with api_client(user, fake) as ac:
            resp = await ac.patch(
                f"/matters/{matter.id}",
                json={"status": "closed"},
                headers=_auth_header(user),
            )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /matters/{matter_id}/access
# ---------------------------------------------------------------------------


class TestListMatterAccess:
    @pytest.mark.asyncio
    async def test_admin_can_list(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        matter = make_matter(firm_id=_FIRM_ID)
        access = make_matter_access(user_id=user.id, matter_id=matter.id)
        fake = FakeSession()
        fake.add_result(matter)  # _verify_matter_in_firm
        fake.add_results_list([access])  # list query
        async with api_client(user, fake) as ac:
            resp = await ac.get(
                f"/matters/{matter.id}/access", headers=_auth_header(user)
            )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    @pytest.mark.asyncio
    async def test_attorney_forbidden(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.attorney)
        fake = FakeSession()
        async with api_client(user, fake) as ac:
            resp = await ac.get(
                f"/matters/{uuid.uuid4()}/access", headers=_auth_header(user)
            )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /matters/{matter_id}/access
# ---------------------------------------------------------------------------


class TestGrantMatterAccess:
    @pytest.mark.asyncio
    async def test_admin_can_grant(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        matter = make_matter(firm_id=_FIRM_ID)
        target = make_user(firm_id=_FIRM_ID, role=Role.attorney)
        fake = FakeSession()
        fake.add_result(matter)  # _verify_matter_in_firm
        fake.add_result(target)  # _verify_user_in_firm
        async with api_client(user, fake) as ac:
            resp = await ac.post(
                f"/matters/{matter.id}/access",
                json={"user_id": str(target.id), "view_work_product": False},
                headers=_auth_header(user),
            )
        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# DELETE /matters/{matter_id}/access/{user_id}
# ---------------------------------------------------------------------------


class TestRevokeMatterAccess:
    @pytest.mark.asyncio
    async def test_admin_can_revoke(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        matter = make_matter(firm_id=_FIRM_ID)
        target = make_user(firm_id=_FIRM_ID, role=Role.attorney)
        access = make_matter_access(user_id=target.id, matter_id=matter.id)
        fake = FakeSession()
        fake.add_result(matter)  # _verify_matter_in_firm
        fake.add_result(access)  # find access row
        async with api_client(user, fake) as ac:
            resp = await ac.delete(
                f"/matters/{matter.id}/access/{target.id}",
                headers=_auth_header(user),
            )
        assert resp.status_code == 200
        assert resp.json()["detail"] == "Access revoked"

    @pytest.mark.asyncio
    async def test_revoke_nonexistent_returns_404(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        matter = make_matter(firm_id=_FIRM_ID)
        fake = FakeSession()
        fake.add_result(matter)  # _verify_matter_in_firm
        fake.add_result(None)  # no access row
        async with api_client(user, fake) as ac:
            resp = await ac.delete(
                f"/matters/{matter.id}/access/{uuid.uuid4()}",
                headers=_auth_header(user),
            )
        assert resp.status_code == 404
