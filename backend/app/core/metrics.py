"""Module-level OTel metric instruments for authentication events.

Import and call these from the auth router (1.4) to record auth activity.
All instruments are created once at module import time.

Usage::

    from app.core.metrics import login_attempts

    login_attempts.add(1, {"result": "success"})
    login_attempts.add(1, {"result": "failure"})
    login_attempts.add(1, {"result": "locked"})
"""

from app.core.telemetry import meter

login_attempts = meter.create_counter(
    "opencase.auth.login_attempts",
    description="Login attempts by result",  # attrs: result=(success|failure|locked)
)

mfa_challenges = meter.create_counter(
    "opencase.auth.mfa_challenges",
    description="MFA TOTP challenge outcomes",  # attrs: result=(success|failure)
)

token_refresh_attempts = meter.create_counter(
    "opencase.auth.token_refresh_attempts",
    description="Token refresh attempts",
)

active_sessions = meter.create_up_down_counter(
    "opencase.auth.active_sessions",
    description="Currently active sessions (access tokens issued minus logouts)",
)
