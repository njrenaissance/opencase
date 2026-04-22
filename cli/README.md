# gideon-cli

Command-line interface for the Gideon API, built on the
[gideon-sdk](../sdk/) Python client.

## Installation

```bash
uv sync
```

The `gideon` command is available in the activated virtual environment.

## Configuration

The CLI resolves settings via a four-layer precedence chain (highest to lowest):

1. **CLI flags** — `gideon --base-url http://api:8000 health`
2. **Environment variables** — `GIDEON_BASE_URL=http://api:8000`
3. **Config file** — `~/.gideon/config.toml`
4. **Defaults** — `http://localhost:8000`, 30s timeout

**Interactive setup:** Run `gideon configure` to set your API URL and timeout interactively.

## Quick Start

```bash
# 1. Set API URL interactively
gideon configure

# 2. Verify the API is reachable
gideon health

# 3. Authenticate (prompts for email, password, and TOTP if MFA is enabled)
gideon login

# 4. List matters you have access to
gideon matter list
```

## Command Reference

### Health & Status
- `gideon health` — API health status
- `gideon ready` — readiness + service dependency checks

### Authentication
- `gideon login` — authenticate (interactive or with `--email`, `--password`, `--totp-code`)
- `gideon logout` — invalidate session and clear local tokens
- `gideon whoami` — show authenticated user, role, and firm

### Multi-Factor Authentication
- `gideon mfa setup` — begin TOTP setup, display secret and provisioning URI
- `gideon mfa confirm` — confirm MFA with a TOTP code
- `gideon mfa disable` — disable MFA with a TOTP code

### Users
- `gideon user list` — list all firm users
- `gideon user get <user-id>` — get user details
- `gideon user create` — create a new user (requires `--email`, `--password`, `--first-name`, `--last-name`, `--role`)
- `gideon user update <user-id>` — update user fields

### Matters (Cases)
- `gideon matter list` — list all matters
- `gideon matter get <matter-id>` — get matter details
- `gideon matter create` — create a new matter (requires `--name`, `--client-id`)
- `gideon matter update <matter-id>` — update matter fields (e.g., `--status`)
- `gideon matter access-list <matter-id>` — list users with access
- `gideon matter access-grant <matter-id>` — grant user access (with optional `--view-work-product`)
- `gideon matter access-revoke <matter-id>` — revoke user access

### Documents
- `gideon document list` — list all documents
- `gideon document get <document-id>` — get document details
- `gideon document upload` — upload a single file (requires `--matter-id` and file path)
- `gideon document bulk-ingest` — upload all supported files from a directory (requires `--matter-id` and directory path)
- `gideon document re-ingest` — re-queue a failed document or all failed documents

### Prompts (AI Chat)
- `gideon prompt list` — list submitted prompts
- `gideon prompt get <prompt-id>` — get prompt details
- `gideon prompt submit` — submit a query to the AI chatbot (requires `--matter-id` and query text)

### Background Tasks
- `gideon task list` — list background tasks (filter with `--status` or `--task-name`)
- `gideon task get <task-id>` — get task details including result and traceback
- `gideon task submit` — submit a background task (requires `--task-name`)
- `gideon task cancel` — cancel a pending or running task

### Firm
- `gideon firm get` — show current firm details

### Utility
- `gideon configure` — set API URL and timeout interactively
- `gideon version` — show CLI and SDK versions

## Global Options

All commands accept these flags:

- `--base-url` (env: `GIDEON_BASE_URL`) — API base URL (default: `http://localhost:8000`)
- `--timeout` (env: `GIDEON_TIMEOUT`) — Request timeout in seconds (default: `30`)
- `--json` — Output as JSON (machine-readable)

## Token Storage

Authentication tokens (access + refresh JWT) are stored securely at `~/.gideon/tokens.json`:
- **Unix/Linux:** mode `0600` (owner-only read/write)
- **Windows:** standard file ACLs apply
- Cleared when you run `gideon logout`

## Full Reference

See [docs/CLI.md](../docs/CLI.md) for the complete CLI reference including all command flags,
detailed examples, option tables, and configuration details.
