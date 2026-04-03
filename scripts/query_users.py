#!/usr/bin/env python3
"""Authenticate via the SDK and list all users."""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

from opencase import OpenCaseClient

load_dotenv()

email = os.environ.get("OPENCASE_ADMIN_EMAIL")
password = os.environ.get("OPENCASE_ADMIN_PASSWORD")
base_url = os.environ.get("OPENCASE_API_URL", "http://localhost:8000")

if not email or not password:
    print("Set OPENCASE_ADMIN_EMAIL and OPENCASE_ADMIN_PASSWORD in .env")
    sys.exit(1)

with OpenCaseClient(base_url=base_url) as client:
    result = client.login(email=email, password=password)

    if hasattr(result, "mfa_required") and result.mfa_required:
        print("MFA required — enter TOTP code to continue.")
        code = input("TOTP code: ")
        client.verify_mfa(mfa_token=result.mfa_token, totp_code=code)

    users = client.list_users()
    for user in users:
        print(f"{user.id}  {user.email}  {user.role}  {user.first_name} {user.last_name}")

    client.logout()
