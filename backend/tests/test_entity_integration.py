"""Integration tests for entity endpoints — runs against Docker Compose stack.

Requires: ``pytest -m integration``

Uses the ``seed_demo`` fixture from conftest.py which creates a firm with
two users, two matters, and access grants, then cleans up after each test.

Access matrix:
    Virginia (attorney) → People v. Smith, People v. Jones
    Jonathan (paralegal) → People v. Jones only
"""

from __future__ import annotations

import httpx
import pytest


def _login(base: str, email: str, password: str) -> dict[str, str]:
    """Login and return auth headers.

    NOTE: Does not handle MFA flow — MFA-enabled users return ``mfa_token``
    instead of ``access_token``, causing a KeyError.
    """
    resp = httpx.post(
        f"{base}/auth/login",
        json={"email": email, "password": password},
        timeout=10,
    )
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ---------------------------------------------------------------------------
# GET /firms/me
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_get_firm(fastapi_service: str, seed_demo: dict) -> None:
    """Any authenticated user can see their firm."""
    headers = _login(
        fastapi_service,
        seed_demo["user_a"]["email"],
        seed_demo["user_a"]["password"],
    )
    resp = httpx.get(f"{fastapi_service}/firms/me", headers=headers, timeout=10)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Demo Firm"
    assert resp.json()["id"] == str(seed_demo["firm_id"])


# ---------------------------------------------------------------------------
# GET /users/me, GET /users/, GET /users/{id}
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_get_current_user(fastapi_service: str, seed_demo: dict) -> None:
    """Any authenticated user can see their own profile."""
    headers = _login(
        fastapi_service,
        seed_demo["user_b"]["email"],
        seed_demo["user_b"]["password"],
    )
    resp = httpx.get(f"{fastapi_service}/users/me", headers=headers, timeout=10)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "jonathan@demofirm.com"
    assert data["role"] == "paralegal"
    # Sensitive fields must not be present
    assert "hashed_password" not in data
    assert "totp_secret" not in data


@pytest.mark.integration
def test_list_users_attorney(fastapi_service: str, seed_demo: dict) -> None:
    """Attorney can list users in the firm."""
    headers = _login(
        fastapi_service,
        seed_demo["user_a"]["email"],
        seed_demo["user_a"]["password"],
    )
    resp = httpx.get(f"{fastapi_service}/users/", headers=headers, timeout=10)
    assert resp.status_code == 200
    emails = [u["email"] for u in resp.json()]
    assert "virginia@demofirm.com" in emails
    assert "jonathan@demofirm.com" in emails


# ---------------------------------------------------------------------------
# GET /matters/ — access filtering
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_attorney_sees_both_matters(fastapi_service: str, seed_demo: dict) -> None:
    """Virginia (attorney) has access to both matters."""
    headers = _login(
        fastapi_service,
        seed_demo["user_a"]["email"],
        seed_demo["user_a"]["password"],
    )
    resp = httpx.get(f"{fastapi_service}/matters/", headers=headers, timeout=10)
    assert resp.status_code == 200
    names = {m["name"] for m in resp.json()}
    assert "People v. Smith" in names
    assert "People v. Jones" in names


@pytest.mark.integration
def test_paralegal_sees_only_assigned_matter(
    fastapi_service: str, seed_demo: dict
) -> None:
    """Jonathan (paralegal) only has access to Matter B."""
    headers = _login(
        fastapi_service,
        seed_demo["user_b"]["email"],
        seed_demo["user_b"]["password"],
    )
    resp = httpx.get(f"{fastapi_service}/matters/", headers=headers, timeout=10)
    assert resp.status_code == 200
    names = [m["name"] for m in resp.json()]
    assert names == ["People v. Jones"]


# ---------------------------------------------------------------------------
# GET /matters/{id} — access enforcement
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_paralegal_cannot_see_unassigned_matter(
    fastapi_service: str, seed_demo: dict
) -> None:
    """Jonathan (paralegal) gets 404 for Matter A (not assigned)."""
    headers = _login(
        fastapi_service,
        seed_demo["user_b"]["email"],
        seed_demo["user_b"]["password"],
    )
    matter_a_id = seed_demo["matter_a"]["id"]
    resp = httpx.get(
        f"{fastapi_service}/matters/{matter_a_id}",
        headers=headers,
        timeout=10,
    )
    assert resp.status_code == 404


@pytest.mark.integration
def test_attorney_can_see_assigned_matter(
    fastapi_service: str, seed_demo: dict
) -> None:
    """Virginia (attorney) can see Matter A detail."""
    headers = _login(
        fastapi_service,
        seed_demo["user_a"]["email"],
        seed_demo["user_a"]["password"],
    )
    matter_a_id = seed_demo["matter_a"]["id"]
    resp = httpx.get(
        f"{fastapi_service}/matters/{matter_a_id}",
        headers=headers,
        timeout=10,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "People v. Smith"


# ---------------------------------------------------------------------------
# RBAC enforcement — create/update require specific roles
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_paralegal_cannot_create_matter(fastapi_service: str, seed_demo: dict) -> None:
    """Paralegal gets 403 when trying to create a matter."""
    headers = _login(
        fastapi_service,
        seed_demo["user_b"]["email"],
        seed_demo["user_b"]["password"],
    )
    resp = httpx.post(
        f"{fastapi_service}/matters/",
        json={
            "name": "Unauthorized Matter",
            "client_id": "00000000-0000-4000-8000-000000000099",
        },
        headers=headers,
        timeout=10,
    )
    assert resp.status_code == 403


@pytest.mark.integration
def test_attorney_can_create_matter(fastapi_service: str, seed_demo: dict) -> None:
    """Attorney can create a new matter."""
    headers = _login(
        fastapi_service,
        seed_demo["user_a"]["email"],
        seed_demo["user_a"]["password"],
    )
    resp = httpx.post(
        f"{fastapi_service}/matters/",
        json={
            "name": "People v. Doe",
            "client_id": "00000000-0000-4000-8000-000000000099",
        },
        headers=headers,
        timeout=10,
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "People v. Doe"


# ---------------------------------------------------------------------------
# Matter access management — admin only
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_attorney_cannot_manage_access(fastapi_service: str, seed_demo: dict) -> None:
    """Attorney gets 403 when trying to list matter access grants."""
    headers = _login(
        fastapi_service,
        seed_demo["user_a"]["email"],
        seed_demo["user_a"]["password"],
    )
    matter_a_id = seed_demo["matter_a"]["id"]
    resp = httpx.get(
        f"{fastapi_service}/matters/{matter_a_id}/access",
        headers=headers,
        timeout=10,
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Admin operations via seed_admin
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    reason="_login() needs MFA flow support for MFA-enabled admin user",
    strict=True,
)
@pytest.mark.integration
def test_admin_can_list_access_and_create_user(
    fastapi_service: str, seed_admin: dict, seed_demo: dict
) -> None:
    """Admin can list matter access and create new users."""
    headers = _login(
        fastapi_service,
        seed_admin["email"],
        seed_admin["password"],
    )

    # Admin can create a user in their own firm
    resp = httpx.post(
        f"{fastapi_service}/users/",
        json={
            "email": "newuser@test.com",
            "password": "NewPassword12345!",
            "first_name": "New",
            "last_name": "User",
            "role": "investigator",
        },
        headers=headers,
        timeout=10,
    )
    assert resp.status_code == 201
    assert resp.json()["role"] == "investigator"
