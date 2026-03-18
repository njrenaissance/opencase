"""Pydantic request/response models for authentication endpoints."""

from pydantic import BaseModel, EmailStr, Field

# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class MfaVerifyRequest(BaseModel):
    mfa_token: str
    totp_code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class MfaConfirmRequest(BaseModel):
    totp_code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105 — not a password


class MfaRequiredResponse(BaseModel):
    mfa_required: bool = True
    mfa_token: str


class MfaSetupResponse(BaseModel):
    totp_secret: str
    provisioning_uri: str


class MfaStatusResponse(BaseModel):
    enabled: bool


class MessageResponse(BaseModel):
    detail: str
