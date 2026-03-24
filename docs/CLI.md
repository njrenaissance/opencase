# OpenCase CLI Reference

The `opencase` command-line tool is the primary admin and developer
interface for interacting with a running OpenCase instance.

## Installation

The CLI is part of the uv workspace. From the repository root:

```bash
uv sync
```

The `opencase` console script is then available in the virtual
environment.

## Configuration

### Precedence

Settings resolve in this order (highest wins):

1. CLI flags (`--base-url`, `--timeout`)
2. Environment variables (`OPENCASE_BASE_URL`, `OPENCASE_TIMEOUT`)
3. Config file (`~/.opencase/config.toml`)
4. Defaults (`http://localhost:8000`, 30 s timeout)

### Interactive setup

```bash
opencase configure
```

Prompts for base URL and timeout, then writes
`~/.opencase/config.toml`.

## Commands

### Health checks (unauthenticated)

```bash
opencase health              # API health status
opencase ready               # Readiness + service dependency checks
```

`ready` exits with code 1 if any dependency is degraded.

### Authentication

```bash
opencase login --email user@firm.com --password secret
opencase login                                          # interactive prompts
opencase login --email user@firm.com --password s --totp-code 123456  # MFA
opencase logout
opencase whoami              # show current user, role, firm
```

After login, tokens are stored in `~/.opencase/tokens.json`
(mode 0600 on Unix). Subsequent commands use them automatically.

### MFA management

```bash
opencase mfa setup           # shows TOTP secret + provisioning URI
opencase mfa confirm --totp-code 123456
opencase mfa disable --totp-code 123456
```

### Users

```bash
opencase user list
opencase user get <user-id>
opencase user create --email j@firm.com --password secret123! \
  --first-name Jane --last-name Doe --role attorney
opencase user update <user-id> --first-name Janet
```

### Matters

```bash
opencase matter list
opencase matter get <matter-id>
opencase matter create --name "People v. Smith" --client-id <uuid>
opencase matter update <matter-id> --status closed
```

### Matter access

```bash
opencase matter access-list <matter-id>
opencase matter access-grant <matter-id> --user-id <uuid>
opencase matter access-grant <matter-id> --user-id <uuid> --view-work-product
opencase matter access-revoke <matter-id> --user-id <uuid>
```

### Documents (stub)

```bash
opencase document list
opencase document get <document-id>
opencase document upload --matter-id <uuid> --filename evidence.pdf \
  --content-type application/pdf --size-bytes 1024 \
  --file-hash <sha256-hex>
opencase document upload --matter-id <uuid> --filename report.pdf \
  --content-type application/pdf --size-bytes 2048 \
  --file-hash <sha256-hex> --source government_production \
  --classification brady --bates-number GOV-001
```

All document endpoints return stub responses. Real upload
(MinIO storage, SHA-256 computation) will be added in Feature 6.

### Prompts (stub)

```bash
opencase prompt list
opencase prompt get <prompt-id>
opencase prompt submit --matter-id <uuid> "What Brady material exists?"
```

All prompt endpoints return stub responses. RAG integration
will be added in Feature 9.

### Firm

```bash
opencase firm get                # show current firm details
```

### Utility

```bash
opencase configure           # interactive connection setup
opencase version             # CLI + SDK versions
```

## JSON output

All commands support `--json` for machine-readable output:

```bash
opencase health --json
opencase whoami --json | jq .email
```

## Token storage

Tokens are persisted to `~/.opencase/tokens.json` with restricted
file permissions (0600 on Unix). `opencase logout` clears this file.

On Windows, standard file ACLs apply (chmod is a no-op).

## Global options

Every command accepts:

| Flag | Env var | Description |
| --- | --- | --- |
| `--base-url` | `OPENCASE_BASE_URL` | API base URL |
| `--timeout` | `OPENCASE_TIMEOUT` | Request timeout (seconds) |
| `--json` | — | Machine-readable JSON output |
