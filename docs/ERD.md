# Gideon — Entity Relationship Diagram

Covers tables through Feature 7.1. Tables from later features
(audit_log, witnesses, disclosure_checklist, etc.) will be added
as each feature lands.

## Core Schema

```mermaid
erDiagram
    firms {
        uuid id PK
        string name
        timestamptz created_at
    }

    users {
        uuid id PK
        uuid firm_id FK
        string email
        string hashed_password
        string title "nullable — e.g. Esq., Dr."
        string first_name
        string middle_initial "nullable"
        string last_name
        enum role "admin | attorney | paralegal | investigator"
        bool is_active "false = account disabled, not deleted"
        string totp_secret "nullable — AES-256-GCM ciphertext"
        bool totp_enabled
        timestamptz totp_verified_at "nullable"
        int failed_login_attempts
        timestamptz locked_until "nullable"
        timestamptz created_at
        timestamptz updated_at
    }

    matters {
        uuid id PK
        uuid firm_id FK
        string name
        uuid client_id
        enum status "open | closed | archived"
        bool legal_hold
        timestamptz created_at
        timestamptz updated_at
    }

    matter_access {
        uuid user_id PK,FK
        uuid matter_id PK,FK
        bool view_work_product
        timestamptz assigned_at
    }

    documents {
        uuid id PK
        uuid firm_id FK
        uuid matter_id FK
        string filename
        string file_hash "SHA-256 hex digest — dedup key"
        string content_type
        int size_bytes
        enum source "government_production | defense | court | work_product"
        enum classification "brady | giglio | jencks | rule16 | work_product | inculpatory | unclassified"
        enum ingestion_status "pending | extracting | chunking | embedding | indexed | failed"
        string bates_number "nullable"
        bool legal_hold
        uuid uploaded_by FK
        timestamptz created_at
        timestamptz updated_at
    }

    firms ||--o{ users : "has"
    firms ||--o{ matters : "owns"
    firms ||--o{ documents : "scoped to"
    users ||--o{ matter_access : "access controlled via"
    matters ||--o{ matter_access : "access controlled via"
    matters ||--o{ documents : "contains"
    users ||--o{ documents : "uploaded by"
```

## Worker Queue Schema

`firm_id` and `user_id` are FKs to the Core Schema `firms` and `users` tables.

```mermaid
erDiagram
    task_submissions {
        string id PK "Celery task ID"
        uuid firm_id FK
        uuid user_id FK
        string task_name "registered name — e.g. ping"
        text args_json "JSON array of positional args"
        text kwargs_json "JSON object of keyword args"
        string status "TaskState enum — pending | started | success | failure | revoked | retry"
        timestamptz submitted_at
    }
```

## Chat Schema

```mermaid
erDiagram
    chat_sessions {
        uuid id PK
        uuid firm_id FK
        uuid matter_id FK
        uuid created_by FK
        string title "nullable — auto-generated or user-set"
        timestamptz created_at
        timestamptz updated_at
    }

    chat_queries {
        uuid id PK
        uuid session_id FK
        uuid user_id FK "who submitted this query"
        text query
        text response "nullable — null while awaiting LLM"
        string model_name "nullable — Ollama model identifier"
        jsonb retrieval_context "nullable — retrieved chunks for citations"
        int tokens_used "nullable"
        int latency_ms "nullable"
        timestamptz created_at
    }

    chat_feedback {
        uuid id PK
        uuid query_id FK
        smallint rating "+1 thumbs up | -1 thumbs down"
        bool flag_bad_citation
        text comment "nullable — free text for prompt tuning"
        timestamptz created_at
    }

    chat_sessions ||--o{ chat_queries : "contains"
    chat_queries ||--o{ chat_feedback : "rated by"
```

`firm_id` and `matter_id` on `chat_sessions` are FKs to the Core Schema.
`firm_id` and `matter_id` are not stored on `chat_queries` — derivable via
`JOIN chat_sessions`. `user_id` on `chat_feedback` is not stored — derivable
via `JOIN chat_queries`.

## Key Constraints

| Table | Constraint | Rule |
| --- | --- | --- |
| `users` | `uq_users_firm_id_email` | Email unique per firm (same email can exist across firms) |
| `users` | `fk_users_firm_id_firms` | Cascades on firm delete |
| `matters` | `fk_matters_firm_id_firms` | Cascades on firm delete |
| `matter_access` | Composite PK `(user_id, matter_id)` | One access row per user/matter pair |
| `matter_access` | `fk_matter_access_user_id_users` | Cascades on user delete |
| `matter_access` | `fk_matter_access_matter_id_matters` | Cascades on matter delete |
| `documents` | `uq_documents_matter_id_file_hash` | Same file (by SHA-256) within same matter is rejected |
| `documents` | `fk_documents_firm_id_firms` | Cascades on firm delete |
| `documents` | `fk_documents_matter_id_matters` | Cascades on matter delete |
| `documents` | `fk_documents_uploaded_by_users` | Cascades on user delete |
| `task_submissions` | `fk_task_submissions_firm_id_firms` | Cascades on firm delete |
| `task_submissions` | `fk_task_submissions_user_id_users` | Cascades on user delete |
| `task_submissions` | `ix_task_submissions_firm_id` | Index on `firm_id` for firm-scoped queries |
| `task_submissions` | `ix_task_submissions_task_name` | Index on `task_name` for filtering |
| `chat_sessions` | `fk_chat_sessions_firm_id_firms` | Cascades on firm delete |
| `chat_sessions` | `fk_chat_sessions_matter_id_matters` | Cascades on matter delete |
| `chat_sessions` | `fk_chat_sessions_created_by_users` | Cascades on user delete |
| `chat_queries` | `fk_chat_queries_session_id_chat_sessions` | Cascades on session delete |
| `chat_queries` | `fk_chat_queries_user_id_users` | Cascades on user delete |
| `chat_feedback` | `uq_chat_feedback_query_id` | One feedback row per query |
| `chat_feedback` | `ck_chat_feedback_rating` | Rating must be -1 or +1 |
| `chat_feedback` | `fk_chat_feedback_query_id_chat_queries` | Cascades on query delete |

## Notes

- All primary keys are UUID v4 — no sequential integers exposed to clients.
- `totp_secret` stores AES-256-GCM ciphertext only — plaintext is never persisted.
- `legal_hold` on a matter blocks document deletion in all downstream services
  (MinIO, Qdrant, Postgres) — enforced by the Legal Hold Celery task (Feature 12).
- `matter_access` is a **security construct**, not a business join table. It is
  checked by `build_qdrant_filter()` on every vector query. A missing row means
  404, not 403 — matter existence is not revealed to unauthorized users.
- `view_work_product` defaults to `false` for all access rows. Only Admin can grant
  it to Paralegal users; Investigators can never receive it (enforced in RBAC layer).
- `role` on `users` is a PostgreSQL native enum (`user_role`). Four roles are fixed
  by design — no `user_roles` lookup table. Roles are a closed set defined by the
  permission model, not operator-configurable data.
- `client_id` is a UUID reference to a client record. The clients table will be
  introduced in a later feature; for now it is stored as a bare UUID.
- `task_submissions.id` is the Celery task ID (a string, not a UUID). The
  primary key is assigned by Celery at submission time.
- `task_submissions.status` is denormalized from the Celery result backend and
  updated on read via `GET /tasks/{task_id}`.
- `chat_queries.retrieval_context` is JSONB with a suggested shape:
  `{"chunks": [{"document_id": "...", "chunk_index": 0, "text": "...",`
  `"score": 0.87}]}`. The exact structure is finalized in Feature 7.5
  (citation assembly).
- `chat_queries.response` is nullable — null while the LLM is generating a response.
  The row is inserted at query time and updated when inference completes.
