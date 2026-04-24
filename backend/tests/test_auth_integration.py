"""Integration tests for auth endpoints — runs against Docker Compose stack.

Requires: ``pytest -m integration``

Uses the ``seed_admin`` fixture from conftest.py which creates a fresh
admin user in the test database and cleans up after each test.
"""

from __future__ import annotations

import httpx
import pyotp
import pytest


@pytest.mark.integration
def test_login_and_logout(
    fastapi_service: str,
    seed_admin: dict,
) -> None:
    """Login → use access token → logout → confirm revoked."""
    base = fastapi_service

    # 1. Login.
    login_resp = httpx.post(
        f"{base}/auth/login",
        json={
            "email": seed_admin["email"],
            "password": seed_admin["password"],
        },
        timeout=10,
    )
    assert login_resp.status_code == 200
    tokens = login_resp.json()
    access = tokens["access_token"]
    refresh = tokens["refresh_token"]
    headers = {"Authorization": f"Bearer {access}"}

    # 2. Verify token works on a protected endpoint.
    setup_resp = httpx.post(
        f"{base}/auth/mfa/setup",
        headers=headers,
        timeout=10,
    )
    assert setup_resp.status_code == 200

    # 3. Logout.
    logout_resp = httpx.post(
        f"{base}/auth/logout",
        json={"refresh_token": refresh},
        headers=headers,
        timeout=10,
    )
    assert logout_resp.status_code == 200

    # 4. Confirm refresh token is revoked.
    refresh_resp = httpx.post(
        f"{base}/auth/refresh",
        json={"refresh_token": refresh},
        timeout=10,
    )
    assert refresh_resp.status_code == 401


@pytest.mark.xfail(reason="MFA flow not implemented yet")
@pytest.mark.integration
def test_full_mfa_flow(
    fastapi_service: str,
    seed_admin: dict,
) -> None:
    """Login → setup MFA → confirm → logout → login with MFA → refresh."""
    base = fastapi_service
    creds = {
        "email": seed_admin["email"],
        "password": seed_admin["password"],
    }

    # 1. Login (no MFA).
    resp = httpx.post(f"{base}/auth/login", json=creds, timeout=10)
    assert resp.status_code == 200
    tokens = resp.json()
    access = tokens["access_token"]
    refresh = tokens["refresh_token"]
    headers = {"Authorization": f"Bearer {access}"}

    # 2. MFA setup.
    setup = httpx.post(
        f"{base}/auth/mfa/setup",
        headers=headers,
        timeout=10,
    )
    assert setup.status_code == 200
    totp_secret = setup.json()["totp_secret"]

    # 3. MFA confirm.
    code = pyotp.TOTP(totp_secret).now()
    confirm = httpx.post(
        f"{base}/auth/mfa/confirm",
        json={"totp_code": code},
        headers=headers,
        timeout=10,
    )
    assert confirm.status_code == 200
    assert confirm.json()["enabled"] is True

    # 4. Logout.
    httpx.post(
        f"{base}/auth/logout",
        json={"refresh_token": refresh},
        headers=headers,
        timeout=10,
    )

    # 5. Login again — MFA required.
    resp2 = httpx.post(f"{base}/auth/login", json=creds, timeout=10)
    assert resp2.status_code == 200
    mfa_data = resp2.json()
    assert mfa_data["mfa_required"] is True

    # 6. MFA verify.
    code2 = pyotp.TOTP(totp_secret).now()
    verify = httpx.post(
        f"{base}/auth/mfa/verify",
        json={
            "mfa_token": mfa_data["mfa_token"],
            "totp_code": code2,
        },
        timeout=10,
    )
    assert verify.status_code == 200
    tokens2 = verify.json()

    # 7. Refresh.
    ref = httpx.post(
        f"{base}/auth/refresh",
        json={"refresh_token": tokens2["refresh_token"]},
        timeout=10,
    )
    assert ref.status_code == 200
    assert ref.json()["access_token"] != tokens2["access_token"]

    # 8. Final logout.
    hdrs = {"Authorization": f"Bearer {ref.json()['access_token']}"}
    final = httpx.post(
        f"{base}/auth/logout",
        json={},
        headers=hdrs,
        timeout=10,
    )
    assert final.status_code == 200


@pytest.mark.integration
def test_invalid_login(
    fastapi_service: str,
    seed_admin: dict,
) -> None:
    """Wrong password returns 401."""
    resp = httpx.post(
        f"{fastapi_service}/auth/login",
        json={
            "email": seed_admin["email"],
            "password": "wrong-password",
        },
        timeout=10,
    )
    assert resp.status_code == 401
