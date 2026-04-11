# Authentication

Feature 1.4 — JWT access/refresh tokens, optional TOTP MFA,
bcrypt password hashing, account lockout.

## Login Flow

```text
┌──────────┐         ┌──────────┐         ┌──────────┐
│  Client  │         │ FastAPI  │         │ Postgres │
└────┬─────┘         └────┬─────┘         └────┬─────┘
     │                    │                    │
     │  POST /auth/login  │                    │
     │  {email, password} │                    │
     │───────────────────>│                    │
     │                    │  SELECT user       │
     │                    │───────────────────>│
     │                    │  user row          │
     │                    │<───────────────────│
     │                    │                    │
     │                    │  verify password   │
     │                    │  check lockout     │
     │                    │                    │
     ├────────────────────┤                    │
     │  IF totp_enabled   │                    │
     │                    │                    │
     │  200 {mfa_required │                    │
     │       mfa_token}   │                    │
     │<───────────────────│                    │
     │                    │                    │
     │  POST /auth/mfa/   │                    │
     │  verify            │                    │
     │  {mfa_token,       │                    │
     │   totp_code}       │                    │
     │───────────────────>│                    │
     │                    │  verify TOTP       │
     │                    │  decrypt secret    │
     ├────────────────────┤                    │
     │  ELSE (no MFA)     │                    │
     │                    │                    │
     │  200 {access_token │  INSERT refresh    │
     │       refresh_token│  token             │
     │       token_type}  │───────────────────>│
     │<───────────────────│                    │
     │                    │                    │
```

## Token Strategy

| Token | Type | TTL | Storage |
| --- | --- | --- | --- |
| Access | Stateless JWT | 15 min | Client only |
| Refresh | Stateful JWT | 7 days | `refresh_tokens` table |
| MFA | Stateless JWT | 5 min | Client only |

Access tokens carry `sub` (user ID), `firm_id`, `role`, and `type`
claims. They are never stored server-side.

Refresh tokens have a `jti` claim that maps to a row in
`refresh_tokens`. On every refresh, the old token is revoked
(token rotation). On logout, all refresh tokens for the user
are revoked.

## MFA Setup Flow

```text
┌──────────┐         ┌──────────┐
│  Client  │         │ FastAPI  │
└────┬─────┘         └────┬─────┘
     │                    │
     │  POST /auth/mfa/   │
     │  setup             │
     │  (Bearer token)    │
     │───────────────────>│
     │                    │
     │  200 {totp_secret  │
     │       provisioning │
     │       _uri}        │
     │<───────────────────│
     │                    │
     │  User scans QR in  │
     │  authenticator app │
     │                    │
     │  POST /auth/mfa/   │
     │  confirm           │
     │  {totp_code}       │
     │───────────────────>│
     │                    │
     │  200 {enabled:true}│
     │<───────────────────│
     │                    │
```

Once confirmed, all future logins require a TOTP code.
Users can disable MFA via `POST /auth/mfa/disable` (requires
a valid TOTP code to prove authenticator possession).

## Endpoints

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| POST | /auth/login | None | Email + password login |
| POST | /auth/mfa/verify | mfa_token in body | Complete MFA challenge |
| POST | /auth/mfa/setup | Bearer token | Generate TOTP secret |
| POST | /auth/mfa/confirm | Bearer token | Verify code, enable MFA |
| POST | /auth/mfa/disable | Bearer token | Verify code, disable MFA |
| POST | /auth/refresh | None | Rotate refresh token |
| POST | /auth/logout | Bearer token | Revoke refresh token(s) |

## Account Lockout

After 5 failed login attempts (configurable via
`GIDEON_AUTH_LOGIN_LOCKOUT_ATTEMPTS`), the account is locked
for 15 minutes (`GIDEON_AUTH_LOGIN_LOCKOUT_MINUTES`).
Locked accounts return HTTP 423. The counter resets on
successful login.

## Password Hashing

Passwords are hashed with bcrypt. The work factor is
configurable via `GIDEON_AUTH_BCRYPT_ROUNDS` (default: 12,
test: 4).

## TOTP Encryption

TOTP secrets are encrypted at rest with AES-256-GCM. The
encryption key is derived from `GIDEON_AUTH_SECRET_KEY`
via HKDF (SHA-256, info=`totp-encryption`). This keeps a
single secret env var while maintaining proper key separation
from JWT signing.

The TOTP digest algorithm is configurable via
`GIDEON_AUTH_TOTP_DIGEST` (sha1, sha256, sha512).
Default is sha1 per RFC 6238.

## Admin Bootstrap

The first admin user is created by the `db-init` Docker
Compose service on initial startup. It reads:

| Env Var | Purpose |
| --- | --- |
| `GIDEON_ADMIN_EMAIL` | Admin email |
| `GIDEON_ADMIN_PASSWORD` | Admin password |
| `GIDEON_ADMIN_FIRST_NAME` | First name |
| `GIDEON_ADMIN_LAST_NAME` | Last name |
| `GIDEON_ADMIN_FIRM_NAME` | Firm name |

The seed script is idempotent — safe to run on every startup.

## Cookie Integration

FastAPI returns tokens in JSON response bodies. The Next.js
frontend stores them in httpOnly secure cookies and attaches
`Authorization: Bearer <token>` when proxying requests to
FastAPI. FastAPI is cookie-unaware.

```text
Browser ──cookie──> Next.js ──Bearer header──> FastAPI
```

## Future

- **Feature 1.4.1** — MS365 OAuth2 login (Microsoft Entra ID)
  for internet-accessible deployments. Trust Entra ID MFA.
- **Passkeys** — WebAuthn/FIDO2 as an additional MFA method.
