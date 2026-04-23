# Gideon Essentials

These are non-negotiable rules specific to Gideon. They protect client
confidentiality, ensure legal compliance, and maintain the integrity of
discovery materials.

---

## Security & Privacy — Non-Negotiable

These rules apply to **every code change**. They cannot be relaxed under any
circumstance.

### 1. No Third-Party LLM API Calls

Gideon runs entirely on-premise. No third-party LLM APIs. Period.

- ❌ BAD: `openai.ChatCompletion.create(...)` or any Anthropic API call

- ✅ GOOD: Use Ollama (configured at `OLLAMA_BASE_URL`)

**Why:** ABA Rule 1.6 — client confidentiality. Training data or logs on
third-party servers violates attorney-client privilege.

### 2. No Model Training on Client Data

Zero retention. LLM inference is stateless.

- ❌ BAD: Logging prompts or responses for "model improvement"

- ✅ GOOD: Ephemeral inference only; no logs, no telemetry, no feedback loops

**Why:** Client materials are privileged. Training on them would be malpractice.

### 3. No External Telemetry

All observability stays on-premise.

- ❌ BAD: Sending traces to Datadog, metrics to Prometheus Cloud, logs to
  CloudWatch

- ✅ GOOD: All logs/metrics/traces in PostgreSQL or on-premise Grafana

**Why:** Prevent accidental leakage of case information to third parties.

### 4. Vector Queries Must Be Matter-Scoped

`build_permissions_filter()` is called on **every single Qdrant query without
exception**. This is the most security-critical function in the codebase.

- ❌ BAD: `qdrant_client.search(collection="documents", query_vector=...)`

- ✅ GOOD:

  ```python
  qdrant_filter = build_permissions_filter(
    user=current_user,
    matter_id=matter_id,
    firm_id=firm_id
  )
  qdrant_client.search(
    collection="documents",
    query_vector=...,
    query_filter=qdrant_filter
  )
  ```

**Why:** A matter-scoped filter prevents one attorney from accessing another
firm's confidential materials. This cannot be bypassed, and the function
signature must never accept client-supplied filter parameters.

### 5. Legal Hold = Immutable

Documents under legal hold cannot be deleted or modified.

- ❌ BAD: Allowing deletion of documents with `legal_hold=true`

- ✅ GOOD: Return 403 Forbidden if deletion is attempted on held documents

**Why:** Legal hold is a court order. Violating it is contempt of court.

### 6. SHA-256 Hash Every Ingested Document

Every document gets a hash for deduplication and integrity verification.

- ❌ BAD: Storing documents without `document_hash`

- ✅ GOOD:

  ```python
  import hashlib
  document_hash = hashlib.sha256(document_content).hexdigest()
  ```

**Why:** Detect tampering, prevent accidental re-ingestion of same documents.

### 7. Immutable Audit Log

All LLM queries, document accesses, and permission changes are logged with
hash chaining.

- ❌ BAD: Deleting audit records or updating them after the fact

- ✅ GOOD: Append-only audit log with hash chain verification

**Why:** Audit trail is evidence. It must be forensically sound.

---

## Legal Compliance

Gideon enforces criminal procedure rules specific to US criminal defense:

### Jurisdiction Scope

- **US Criminal Defense** — Defense-side discovery obligations only

- **NY State + Federal Courts:**
  - NY CPL Article 245 — NY discovery obligations and disclosure clocks
  - CPL 30.30 — Speedy trial clocks
  - Brady v. Maryland — Exculpatory evidence disclosure
  - Giglio v. United States — Witness impeachment material disclosure
  - Jencks Act — Prior statements of government witnesses
  - FRCP Rule 16 — Federal criminal discovery

### Not In Scope

- Prosecution-side obligations (this is not an ADA tool)

- Civil discovery

- Family law, immigration, admin law

- Multi-jurisdiction (Gideon focuses on NY)

- HIPAA/healthcare (no special medical evidence handling)

**Why:** Scope limits complexity and reduces compliance risk. Expanding to
other jurisdictions or roles requires legal review.

---

## Domain Constraints

### Four User Roles

Gideon has exactly four roles with specific permissions:

| Role | Work Product | Jencks | Matter Access |
| --- | --- | --- | --- |
| Admin | Yes | Yes | All matters |
| Attorney | Yes | Yes | Assigned matters |
| Paralegal | If granted | Yes | Assigned matters |
| Investigator | No | No | Assigned matters |

- ❌ BAD: Adding a "junior attorney" or "counsel" role

- ✅ GOOD: Grant permissions via `view_work_product` flag or matter assignment

**Why:** Scope. More roles = more permission matrix rows = more bugs. Use flags
and assignments instead.

### Jencks Material Gating

Jencks material (prior statements of government witnesses) is hidden until the
witness has testified.

- ❌ BAD: Returning Jencks documents before `witness.has_testified = true`

- ✅ GOOD: Filter by `has_testified` flag in `build_permissions_filter()`

**Why:** Jencks Act rule. Prior statements must not be disclosed pre-testimony
(would be impeachment material).

---

## Git Workflow for Gideon

### Branch Naming

```text
<type>/<issue-number>-<description>
```

- `feat/42-bulk-document-upload`

- `fix/118-qdrant-filter-bypass`

- `docs/116-update-quickstart`

- `security/120-add-mfa-enforcement`

**Why:** Each branch ties to one GitHub issue. Easy to link PRs to work items.

### Conventional Commits

```text
<type>[optional scope]: <description>
```

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`,
`ci`, `chore`, `revert`

**Breaking Changes:** Append `!` or include `BREAKING CHANGE:` footer.

**Examples:**

- `feat: add Brady tracker dashboard` → minor version bump (0.X.0)

- `fix(qdrant): fix matter-scope filter bypass` → patch version bump (0.0.X)

- `feat!: redesign permission model` → major version bump (X.0.0)

**Why:** Automated releases. Tool scans commit messages and bumps versions.

### Commit Size

One logical change per commit. Small, focused commits are easier to review,
bisect, and understand.

- ❌ BAD: One commit with "implement Brady tracker, add MFA, refactor auth"

- ✅ GOOD: Three separate commits

### Issue Tracking

Work is tracked in GitHub Issues, not TODO comments in code.

- ❌ BAD: `// TODO: fix qdrant filter bypass`

- ✅ GOOD: GitHub Issue #118 with the same description

When referencing an issue in a commit, use:

```text
fixes #118
```

or

```text
relates to #118
```

in the commit message footer.

### Git Worktrees

Use [git worktrees](<https://git-scm.com/docs/git-worktree>) for parallel work on
multiple issues. Each worktree opens as a separate VS Code window.

```bash
git worktree add .git/worktrees/issue-42 -b feature/42-bulk-upload
cd .git/worktrees/issue-42

```

Optionally, use
[Peacock](<https://marketplace.visualstudio.com/items?itemName=johnpapa.vscode-peacock>)
to color-code windows so you can distinguish them at a glance.

---

## Language & Framework Standards

### Python

- **Version**: Python 3.12+

- **Formatter**: `ruff format backend/`

- **Linter**: `ruff check backend/`

- **Type checker**: `mypy backend/`

- **Type hints**: Required on all public functions

- **Test runner**: `pytest` with `pytest-bdd` for BDD scenarios

Run before committing:

```bash
uv run ruff format backend/
uv run ruff check backend/
uv run mypy backend/
uv run pytest backend/tests/

```

### TypeScript

- **Version**: Node 20+

- **Type checking**: Strict TypeScript (`strict: true` in tsconfig.json)

- **Formatter**: Prettier

- **Linter**: ESLint

- **Test runner**: Vitest (with `it.each` for parametrized tests)

Configure your editor to format on save with Prettier.

### Markdown

- **Linter**: markdownlint (see `.markdownlint.json`)

- **Line length**: 80 characters (hard wrap)

- **Code blocks**: Must specify language (`` ```python `` not ` ``` `)

---

## DRY Principle

If extracting shared code reduces administrative overhead (fewer places to
update when something changes), do it. Prefer shared helpers, context
managers, and base utilities over copy-paste.

**However:** Three similar lines is better than a premature abstraction. Do not
extract code purely for the sake of reducing duplication if:

- The extracted function is used in only one place

- The context is fundamentally different (e.g., test helpers vs. production code)

- Extraction makes the code harder to understand

---

## Testing Standards

### Parametrized Tests

Use parametrized tests when testing the same outcome across different inputs.
Do not write separate test functions that only differ by which field has a bad
value.

**Python:**

```python
@pytest.mark.parametrize("field,value", [
    ("email", "invalid"),
    ("phone", ""),
    ("name", None),
])
def test_validation_rejects_bad_input(field, value):
    # single test body

```

**TypeScript:**

```typescript
it.each([
  ["email", "invalid"],
  ["phone", ""],
  ["name", null],
])("rejects invalid %s", (field, value) => {
  // single test body
});

```

### Fixtures & Shared Helpers

Use fixtures (in `conftest.py` for Python) to reduce setup/teardown boilerplate.
Repeated setup/teardown logic should be extracted into context managers or
fixtures rather than duplicated in every test function.

### Pre-Commit Dedup Check

Before committing, review all files in the changeset for functions that share
the same name, signature, and purpose. If duplicates exist across files, move
them into a single shared function in the appropriate module (e.g.,
`tests/factories.py` for test helpers).

Do not commit files containing duplicate function definitions.

---

## BDD Test Structure

Tests are written in Gherkin and executed with `pytest-bdd`.

```text
backend/
└── tests/
    ├── features/
    │   ├── ingestion/
    │   ├── chatbot/
    │   ├── brady_tracker/
    │   ├── document_review/
    │   ├── witness_index/
    │   ├── rbac/
    │   └── audit/
    └── step_defs/
        ├── ingestion/
        ├── chatbot/
        └── ...

```

Each `.feature` file maps to one MVP feature area. Step definitions live in
matching subdirectories under `step_defs/`.

---

## See Also

- **[Clean Code Principles](clean-code.md)** — Universal rules for writing
  maintainable code

- **[Clean Architecture](clean-architecture.md)** — SOLID principles and
  architectural patterns

- **[Design Patterns](design-patterns.md)** — 11 most-used patterns with
  Gideon examples
