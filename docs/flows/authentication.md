# Data Flow: Authentication

**Overview:** A user logs in with email and password, enrolls in MFA, and receives a session. Subsequent requests authenticate via JWT (for API calls) or httpOnly session cookies (for the UI). All authentication is local — no external identity providers.

---

## High-Level Sequence

### Initial Login + MFA Setup

```mermaid
sequenceDiagram
    actor User
    participant Browser as Browser
    participant API as API Layer
    participant Auth as Auth & Permissions<br/>Layer
    participant Data as Data Layer<br/>(PostgreSQL)

    User->>Browser: Navigate to /login
    Browser->>API: GET /login (redirects to Next.js)
    API->>Browser: Login page

    User->>Browser: Enter email + password
    Browser->>API: POST /auth/login
    API->>Auth: validate_password()
    Auth->>Data: Look up user by email
    Data->>Auth: User + hashed_password
    Auth->>Auth: bcrypt.compare()<br/>(timing-safe)
    alt Invalid password
        Auth->>API: 401 Unauthorized
        API->>Browser: Error: Invalid credentials
    else Valid password
        Auth->>Auth: Check if MFA enrolled
        alt MFA not enrolled
            Auth->>Auth: Generate TOTP secret<br/>(AES-256-GCM)
            Auth->>Data: Update user: mfa_secret,<br/>mfa_enabled=false
            Auth->>API: Return QR code + backup codes
            API->>Browser: Display QR code + instructions
        else MFA already enrolled
            Auth->>API: Prompt for TOTP
            API->>Browser: MFA verification form
        end
    end

    User->>Browser: Scan QR code<br/>Enter TOTP from app
    Browser->>API: POST /auth/mfa/enroll<br/>(totp_code)
    API->>Auth: verify_totp()
    Auth->>Auth: Calculate HOTP<br/>from secret
    alt TOTP matches
        Auth->>Data: Update user: mfa_enabled=true
        Auth->>Auth: Create JWT token<br/>(HS256, exp=1h)
        Auth->>Auth: Create refresh token<br/>(random, exp=30d)
        Auth->>Data: Store refresh token hash
        Auth->>API: Return JWT + refresh token
        API->>Browser: Set httpOnly cookie (session)
        API->>Browser: Store JWT in memory (API calls)
        API->>Browser: Redirect to /dashboard
    else TOTP invalid
        Auth->>API: 401 Unauthorized
        API->>Browser: Error: Invalid TOTP
    end
```

### Subsequent Requests (JWT/Session)

```mermaid
sequenceDiagram
    actor User
    participant Browser as Browser
    participant API as API Layer
    participant Auth as Auth & Permissions<br/>Layer

    User->>Browser: Click "Search Documents"
    Browser->>Browser: Retrieve JWT from memory
    Browser->>API: GET /documents<br/>Header: Authorization: Bearer {JWT}
    API->>Auth: Verify JWT signature (HS256)
    alt JWT valid
        Auth->>Auth: Extract user_id, roles, exp
        Auth->>Auth: Check expiration
        alt JWT expired
            Auth->>API: 401 Unauthorized
            API->>Browser: Redirect to /login
        else JWT fresh
            Auth->>API: Pass user context to router
            API->>Browser: Return documents (filtered by user's matter access)
        end
    else JWT signature invalid
        Auth->>API: 403 Forbidden
        API->>Browser: Error: Unauthorized
    end
```

---

## Step-by-Step Walkthrough

### 1. **User Login Request** (API Layer)

User submits email + password to `POST /auth/login`:

```json
{
  "email": "attorney@firm.com",
  "password": "secure_password_here"
}
```

The API router (`api/auth.py`) receives and delegates to `core/auth.py`.

### 2. **Password Validation** (Auth & Permissions Layer)

The auth module performs:

```python
# 1. Look up user by email
user = await db.query(User).filter_by(email=email).first()
if not user:
    raise 401 Unauthorized  # Prevent email enumeration

# 2. Timing-safe bcrypt comparison
if not bcrypt.checkpw(password.encode(), user.password_hash):
    raise 401 Unauthorized

# 3. Check if MFA is enrolled
if not user.mfa_enabled:
    return {
        "status": "mfa_required",
        "mfa_secret": generate_mfa_secret(),
        "qr_code": generate_qr_code_url(...)
    }
else:
    return {
        "status": "mfa_verification_required"
    }
```

**Timing Safety:** bcrypt is deliberately slow (configurable cost factor) and constant-time, preventing timing attacks.

### 3. **MFA Enrollment (if not yet enrolled)**

The API returns a QR code (via `pyotp`):

```python
import pyotp

secret = pyotp.random_base32()  # e.g., "JBSWY3DPEB3GG64TMMQ"
# Encrypt secret before storing:
encrypted_secret = encrypt_aes_256_gcm(secret, user_password)

totp = pyotp.TOTP(secret)
qr_uri = totp.provisioning_uri(
    name=user.email,
    issuer_name="Gideon"
)
# User scans QR into authenticator app (Google Authenticator, Authy, etc.)
```

The user installs an authenticator app, scans the QR code, and gets a 6-digit TOTP code.

### 4. **MFA Verification** (Auth & Permissions Layer)

User submits TOTP code to `POST /auth/mfa/verify`:

```json
{
  "email": "attorney@firm.com",
  "totp_code": "123456"
}
```

The auth module verifies:

```python
user = await db.query(User).filter_by(email=email).first()
secret = decrypt_aes_256_gcm(user.mfa_secret, user_password)

totp = pyotp.TOTP(secret)
if not totp.verify(totp_code, valid_window=1):
    raise 401 Unauthorized  # Invalid TOTP

# TOTP valid; create session
return {
    "status": "authenticated",
    "jwt": create_jwt_token(user),
    "refresh_token": generate_refresh_token(user),
}
```

**TOTP Validation:**

- TOTP is time-based (30-second windows)
- `valid_window=1` allows ±1 window (60 seconds total tolerance) to account for clock skew
- Each TOTP code can only be used once (prevents replay attacks)

### 5. **JWT Token Creation** (Auth & Permissions Layer)

Create a signed JWT using HS256 (HMAC-SHA256):

```python
import jwt
from datetime import datetime, timedelta

payload = {
    "user_id": user.id,
    "email": user.email,
    "firm_id": user.firm_id,
    "roles": [role.name for role in user.roles],  # ["admin", "attorney"]
    "iat": datetime.utcnow(),
    "exp": datetime.utcnow() + timedelta(hours=1),  # 1-hour expiration
}

token = jwt.encode(
    payload,
    settings.auth.jwt_secret,  # Should be ≥32 bytes
    algorithm="HS256"
)
```

**JWT Claims:**

- `user_id`: Unique user identifier (for lookups)
- `email`: User's email (for audits)
- `firm_id`: Firm scope (for multi-tenant filtering)
- `roles`: User's roles (for RBAC decisions)
- `iat`, `exp`: Issued-at and expiration (for freshness validation)

**Secret Management:** `settings.auth.jwt_secret` is loaded from environment variable `GIDEON_JWT_SECRET`. It should be:

- At least 32 bytes (256 bits)
- Randomly generated (not hardcoded)
- Rotated periodically (V2 feature)

### 6. **Refresh Token Creation** (Auth & Permissions Layer)

Create a separate refresh token for long-lived sessions:

```python
refresh_token = secrets.token_urlsafe(32)
refresh_token_hash = sha256_hash(refresh_token)

# Store hash (not the token itself) in PostgreSQL
refresh_token_record = RefreshToken(
    user_id=user.id,
    token_hash=refresh_token_hash,
    created_at=datetime.utcnow(),
    expires_at=datetime.utcnow() + timedelta(days=30)
)
db.add(refresh_token_record)
db.commit()

return refresh_token  # Return raw token to client (never stored plaintext)
```

**Why Hashing?** The refresh token is hashed before storage, like passwords. The client stores it (securely), and only provides the hash-equivalent on token refresh.

### 7. **Return Tokens** (API → Browser)

The API returns:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "dGhpc2lzYXJhbmRvbXRva2VuYXNleGFtcGxlMQ=="
}
```

The Next.js frontend:

1. Stores the **access_token** in memory (not localStorage/sessionStorage to prevent XSS theft)
2. Stores the **refresh_token** in a `HttpOnly` cookie (inaccessible to JavaScript; only sent with HTTP requests)
3. Includes the access_token in subsequent API request headers: `Authorization: Bearer {token}`

### 8. **Session Cookie (HttpOnly)** (API → Browser)

The API also sets an httpOnly cookie:

```python
response.set_cookie(
    key="session",
    value=session_id,
    max_age=30 * 24 * 60 * 60,  # 30 days
    httponly=True,  # JavaScript cannot access
    secure=True,  # HTTPS only
    samesite="Lax"  # CSRF protection
)
```

This cookie is automatically sent with every request and can be used as a fallback for authentication if the JWT is lost.

### 9. **Subsequent API Requests** (JWT Verification)

For every subsequent request, the client includes:

```http
GET /documents HTTP/1.1
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
Cookie: session=session_id_here
```

The API router uses a FastAPI dependency (`get_current_user`):

```python
async def get_current_user(
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db)
) -> User:
    if not authorization.startswith("Bearer "):
        raise 401 Unauthorized

    token = authorization[7:]  # Strip "Bearer "

    try:
        payload = jwt.decode(
            token,
            settings.auth.jwt_secret,
            algorithms=["HS256"]
        )
    except jwt.ExpiredSignatureError:
        raise 401 Unauthorized  # Token expired; client should refresh
    except jwt.InvalidSignatureError:
        raise 403 Forbidden  # Token tampered with

    # Token is valid; extract user_id and fetch from DB
    user = await db.query(User).get(payload["user_id"])
    if not user or user.deleted_at:
        raise 401 Unauthorized

    return user
```

### 10. **Token Refresh** (JWT Rotation)

When the access token is about to expire (or has expired), the client calls `POST /auth/refresh`:

```python
@router.post("/auth/refresh")
async def refresh_token(
    refresh_token: str,
    db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    refresh_token_hash = sha256_hash(refresh_token)
    record = await db.query(RefreshToken).filter_by(
        token_hash=refresh_token_hash
    ).first()

    if not record or record.expires_at < datetime.utcnow():
        raise 401 Unauthorized  # Refresh token expired or invalid

    user = record.user
    new_access_token = create_jwt_token(user)

    return TokenResponse(
        access_token=new_access_token,
        expires_in=3600
    )
```

---

## Key Decision Points

1. **MFA Mandatory:** All users must enroll in TOTP MFA on first login. No exceptions. This is a security requirement per ABA Opinion 512.

2. **TOTP Storage:** Secrets are encrypted at rest using AES-256-GCM (derived from user password). If the password is changed, the secret is re-encrypted.

3. **JWT Expiration:** Short-lived (1 hour). Reduces exposure if a token is stolen. Clients must refresh before expiration.

4. **Refresh Token Storage:** Hashed and stored in PostgreSQL. Can be revoked (blacklisted) without redeploying.

5. **No External IdP:** Gideon never delegates to Google, Okta, or any external identity provider. All identity is local. This ensures no third-party access to user data.

6. **Password Requirements:** Minimum 12 characters, 1 uppercase, 1 lowercase, 1 digit, 1 special char (enforced client-side + server-side).

---

## Error Handling

| Scenario | Response | Action |
| --- | --- | --- |
| Email not found | 401 Unauthorized | Do not reveal if email exists (prevent enumeration) |
| Password incorrect | 401 Unauthorized | Log failed attempt; lock account after 5 attempts |
| TOTP invalid | 401 Unauthorized | Allow retry; no account lockout for TOTP |
| JWT expired | 401 Unauthorized | Client should call `/auth/refresh` |
| JWT signature invalid | 403 Forbidden | Possible token tampering; log security event |
| MFA device lost | Manual admin reset | Admin can disable MFA for user; user must re-enroll |

---

## Account Lockout (Brute Force Protection)

After 5 failed password attempts, account is locked for 15 minutes:

```python
if user.failed_login_attempts >= 5:
    if datetime.utcnow() < user.locked_until:
        raise 429 Too Many Requests
    else:
        user.failed_login_attempts = 0
        user.locked_until = None
```

Failed attempts are logged for audit purposes.

---

## Session Timeout

Sessions expire after **inactivity timeout** (default 30 minutes):

```python
if datetime.utcnow() - user.last_activity > timedelta(minutes=30):
    revoke_session()
    raise 401 Unauthorized  # Session expired
```

User activity (any API request) resets the timeout.

---

## Compliance & Security

- **ABA Opinion 512:** Requires MFA for all users. ✅
- **ABA Rule 1.6:** Client confidentiality. ✅ Local auth prevents third-party data leakage.
- **NIST SP 800-132:** Password hashing (bcrypt). ✅
- **NIST SP 800-63B:** TOTP (RFC 6238). ✅
- **OWASP:** No tokens in URL, httpOnly cookies, CSRF tokens. ✅

---

## Related Flows

- [Permission Filtering](permission-filtering.md) — How user roles (from JWT) enforce access control
- [RAG Query](rag-query.md) — How user context is passed to the RAG pipeline
