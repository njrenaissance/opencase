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

# ---------------------------------------------------------------------------
# RBAC (Feature 1.5)
# ---------------------------------------------------------------------------

access_denied = meter.create_counter(
    "opencase.rbac.access_denied",
    description="RBAC access denials",  # attrs: reason=(role|matter), role=<role>
)

# ---------------------------------------------------------------------------
# Entity management (Feature 14)
# ---------------------------------------------------------------------------

users_created = meter.create_counter(
    "opencase.users.created",
    description="Users created",
)

users_updated = meter.create_counter(
    "opencase.users.updated",
    description="Users updated",
)

matters_created = meter.create_counter(
    "opencase.matters.created",
    description="Matters created",
)

matters_updated = meter.create_counter(
    "opencase.matters.updated",
    description="Matters updated",
)

matter_access_granted = meter.create_counter(
    "opencase.matter_access.granted",
    description="Matter access grants",
)

matter_access_revoked = meter.create_counter(
    "opencase.matter_access.revoked",
    description="Matter access revocations",
)

# ---------------------------------------------------------------------------
# Documents (Feature 1.8)
# ---------------------------------------------------------------------------

documents_created = meter.create_counter(
    "opencase.documents.created",
    description="Documents created",
)

# ---------------------------------------------------------------------------
# Prompts (Feature 1.8)
# ---------------------------------------------------------------------------

prompts_created = meter.create_counter(
    "opencase.prompts.created",
    description="Prompts submitted",
)
