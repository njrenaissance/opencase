"""Unit tests for firm, user, matter, and matter_access API endpoints.

Uses AsyncClient + in-memory overrides via shared FakeSession / api_client
from conftest.py.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from shared.models.enums import Role

from tests.conftest import FakeSession, api_client, auth_header
from tests.factories import make_firm, make_matter, make_matter_access, make_user

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_FIRM_ID = uuid.uuid4()
_NOW = datetime.now(UTC)


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
            resp = await ac.get("/firms/me", headers=auth_header(user))
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
            resp = await ac.get("/users/me", headers=auth_header(user))
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
            resp = await ac.get("/users/", headers=auth_header(user))
        assert resp.status_code == 200
        assert len(resp.json()) == 2  # noqa: PLR2004

    @pytest.mark.asyncio
    async def test_investigator_forbidden(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.investigator)
        fake = FakeSession()
        async with api_client(user, fake) as ac:
            resp = await ac.get("/users/", headers=auth_header(user))
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
            resp = await ac.get(f"/users/{target.id}", headers=auth_header(user))
        assert resp.status_code == 200
        assert resp.json()["id"] == str(target.id)

    @pytest.mark.asyncio
    async def test_cross_firm_returns_404(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()
        fake.add_result(None)  # not found in firm
        async with api_client(user, fake) as ac:
            resp = await ac.get(f"/users/{uuid.uuid4()}", headers=auth_header(user))
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /users/
# ---------------------------------------------------------------------------


class TestCreateUser:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "middle_initial,expected",
        [
            (None, None),
            ("B", "B"),
        ],
        ids=["without_middle_initial", "with_middle_initial"],
    )
    async def test_admin_can_create(
        self, middle_initial: str | None, expected: str | None
    ) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()
        payload = {
            "email": "new@firm.com",
            "password": "a-long-password",
            "first_name": "New",
            "last_name": "User",
            "role": "paralegal",
        }
        if middle_initial is not None:
            payload["middle_initial"] = middle_initial
        async with api_client(user, fake) as ac:
            resp = await ac.post(
                "/users/",
                json=payload,
                headers=auth_header(user),
            )
        assert resp.status_code == 201
        assert resp.json()["middle_initial"] == expected

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
                headers=auth_header(user),
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
                headers=auth_header(user),
            )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "patch_payload,expected_middle_initial",
        [
            ({"middle_initial": "C"}, "C"),
            ({"middle_initial": None}, None),
        ],
        ids=["set_middle_initial", "clear_middle_initial"],
    )
    async def test_update_middle_initial(
        self,
        patch_payload: dict,
        expected_middle_initial: str | None,
    ) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        target = make_user(firm_id=_FIRM_ID, role=Role.attorney, middle_initial="A")
        fake = FakeSession()
        fake.add_result(target)
        async with api_client(user, fake) as ac:
            resp = await ac.patch(
                f"/users/{target.id}",
                json=patch_payload,
                headers=auth_header(user),
            )
        assert resp.status_code == 200
        assert resp.json()["middle_initial"] == expected_middle_initial

    @pytest.mark.asyncio
    async def test_self_deactivation_rejected(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()
        fake.add_result(user)  # found self
        async with api_client(user, fake) as ac:
            resp = await ac.patch(
                f"/users/{user.id}",
                json={"is_active": False},
                headers=auth_header(user),
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
                headers=auth_header(user),
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
            resp = await ac.get("/matters/", headers=auth_header(user))
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
            resp = await ac.get(f"/matters/{matter.id}", headers=auth_header(user))
        assert resp.status_code == 200
        assert resp.json()["name"] == matter.name

    @pytest.mark.asyncio
    async def test_not_found(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.admin)
        fake = FakeSession()
        fake.add_result(None)
        async with api_client(user, fake) as ac:
            resp = await ac.get(f"/matters/{uuid.uuid4()}", headers=auth_header(user))
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
                headers=auth_header(user),
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
                headers=auth_header(user),
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
                headers=auth_header(user),
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
                f"/matters/{matter.id}/access", headers=auth_header(user)
            )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    @pytest.mark.asyncio
    async def test_attorney_forbidden(self) -> None:
        user = make_user(firm_id=_FIRM_ID, role=Role.attorney)
        fake = FakeSession()
        async with api_client(user, fake) as ac:
            resp = await ac.get(
                f"/matters/{uuid.uuid4()}/access", headers=auth_header(user)
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
                headers=auth_header(user),
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
                headers=auth_header(user),
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
                headers=auth_header(user),
            )
        assert resp.status_code == 404
