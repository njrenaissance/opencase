# Gideon CLI Reference

The `gideon` command-line tool is the primary admin and developer
interface for interacting with a running Gideon instance.

## Installation

The CLI is part of the uv workspace. From the repository root:

```bash
uv sync
```

The `gideon` console script is then available in the virtual
environment.

## Configuration

### Precedence

Settings resolve in this order (highest wins):

1. CLI flags (`--base-url`, `--timeout`)
2. Environment variables (`GIDEON_BASE_URL`, `GIDEON_TIMEOUT`)
3. Config file (`~/.gideon/config.toml`)
4. Defaults (`http://localhost:8000`, 30 s timeout)

### Interactive setup

```bash
gideon configure
```

Prompts for base URL and timeout, then writes
`~/.gideon/config.toml`.

## Commands

### Health checks (unauthenticated)

```bash
gideon health              # API health status
gideon ready               # Readiness + service dependency checks
```

`ready` exits with code 1 if any dependency is degraded.

### Authentication

```bash
gideon login --email user@firm.com --password secret
gideon login                                          # interactive prompts
gideon login --email user@firm.com --password s --totp-code 123456  # MFA
gideon logout
gideon whoami              # show current user, role, firm
```

After login, tokens are stored in `~/.gideon/tokens.json`
(mode 0600 on Unix). Subsequent commands use them automatically.

### MFA management

```bash
gideon mfa setup           # shows TOTP secret + provisioning URI
gideon mfa confirm --totp-code 123456
gideon mfa disable --totp-code 123456
```

### Users

```bash
gideon user list
gideon user get <user-id>
gideon user create --email j@firm.com --password secret123! \
  --first-name Jane --last-name Doe --role attorney
gideon user update <user-id> --first-name Janet
```

### Matters

```bash
gideon matter list
gideon matter get <matter-id>
gideon matter create --name "People v. Smith" --client-id <uuid>
gideon matter update <matter-id> --status closed
```

### Matter access

```bash
gideon matter access-list <matter-id>
gideon matter access-grant <matter-id> --user-id <uuid>
gideon matter access-grant <matter-id> --user-id <uuid> --view-work-product
gideon matter access-revoke <matter-id> --user-id <uuid>
```

### Tasks

```bash
gideon task list                          # list all tasks for current firm
gideon task list --status pending         # filter by state
gideon task list --task-name ping         # filter by registered task name
gideon task get <task-id>                 # full task detail + live Celery status
gideon task submit --task-name ping       # submit a registered task
gideon task cancel <task-id>              # revoke a pending/running task
```

Task submission requires Admin or Attorney role. Cancel and update
require Admin. List and get are available to any authenticated user.

Only tasks registered in `TASK_REGISTRY` can be submitted via the
API. Currently registered: `ping`.

### Documents

```bash
# List all documents accessible to the current user
gideon document list
gideon document list --json

# Get metadata for a single document
gideon document get <document-id>

# Upload a single file to a matter
gideon document upload ./evidence.pdf --matter-id <uuid>
gideon document upload ./report.pdf --matter-id <uuid> \
  --source government_production --classification brady \
  --bates-number GOV-001

# Bulk-ingest all supported files from a local directory
gideon document bulk-ingest ./discovery-folder --matter-id <uuid>
gideon document bulk-ingest ./discovery-folder --matter-id <uuid> \
  --source government_production --classification unclassified

# Preview which files would be ingested (no upload)
gideon document bulk-ingest ./discovery-folder --matter-id <uuid> --dry-run

# Non-recursive (top-level files only, skip subdirectories)
gideon document bulk-ingest ./discovery-folder --matter-id <uuid> --no-recursive

# JSON output (machine-readable per-file results)
gideon document bulk-ingest ./discovery-folder --matter-id <uuid> --json
```

**Upload** accepts a file path as a positional argument. The server
computes the SHA-256 hash, checks for duplicates within the matter,
stores the original in MinIO, and returns the document metadata.

**Bulk-ingest** recursively walks a directory (by default), filters to
supported file types (PDF, Word, Excel, PowerPoint, RTF, text, CSV,
HTML, and common image formats), and uploads each file sequentially.

Before uploading, the CLI hashes each file locally and calls the
`/documents/check-duplicate` endpoint. Files that already exist in the
matter are skipped without uploading, saving bandwidth on re-runs.

The summary line reports uploaded, skipped (duplicate), and failed
counts. The exit code is 0 if all files succeeded or were skipped, and
1 if any file failed.

| Option | Default | Description |
| --- | --- | --- |
| `--matter-id` | **required** | Target matter UUID |
| `--source` | `defense` | Document source (`defense`, `government_production`, `court`, `work_product`) |
| `--classification` | `unclassified` | Document classification |
| `--recursive / --no-recursive` | `--recursive` | Walk subdirectories |
| `--dry-run` | off | List files without uploading |
| `--bates-number` | none | Bates number (single upload only) |

### Prompts (stub)

```bash
gideon prompt list
gideon prompt get <prompt-id>
gideon prompt submit --matter-id <uuid> "What Brady material exists?"
```

All prompt endpoints return stub responses. RAG integration
will be added in Feature 9.

### Firm

```bash
gideon firm get                # show current firm details
```

### Utility

```bash
gideon configure           # interactive connection setup
gideon version             # CLI + SDK versions
```

## JSON output

All commands support `--json` for machine-readable output:

```bash
gideon health --json
gideon whoami --json | jq .email
```

## Token storage

Tokens are persisted to `~/.gideon/tokens.json` with restricted
file permissions (0600 on Unix). `gideon logout` clears this file.

On Windows, standard file ACLs apply (chmod is a no-op).

## Global options

Every command accepts:

| Flag | Env var | Description |
| --- | --- | --- |
| `--base-url` | `GIDEON_BASE_URL` | API base URL |
| `--timeout` | `GIDEON_TIMEOUT` | Request timeout (seconds) |
| `--json` | — | Machine-readable JSON output |
