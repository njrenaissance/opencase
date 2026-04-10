#!/usr/bin/env python3
"""Authenticate via the SDK and list all users."""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

from opencase import Client


def main() -> None:
    load_dotenv()

    email = os.environ.get("OPENCASE_ADMIN_EMAIL")
    password = os.environ.get("OPENCASE_ADMIN_PASSWORD")
    base_url = os.environ.get("OPENCASE_API_URL", "http://localhost:8000")

    if not email or not password:
        print("Set OPENCASE_ADMIN_EMAIL and OPENCASE_ADMIN_PASSWORD in .env")
        sys.exit(1)

    with Client(base_url=base_url) as client:
        result = client.login(email=email, password=password)

        if getattr(result, "mfa_required", False):
            print("MFA required — enter TOTP code to continue.")
            code = input("TOTP code: ")
            mfa_token = getattr(result, "mfa_token", None)
            if not mfa_token:
                sys.exit("MFA required but no mfa_token in login response")
            client.verify_mfa(mfa_token=mfa_token, totp_code=code)

        users = client.list_users()
        for user in users:
            print(f"{user.id}  {user.email}  {user.role}  {user.first_name} {user.last_name}")

        client.logout()


if __name__ == "__main__":
    main()
