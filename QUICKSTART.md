# Persistent Environment Setup

For setting up a persistent Gideon instance to ingest and work with
documents (not for unit or integration testing).

## Update Environment Variables

Copy `.env.example` to `.env` and update required values:

```bash
cp .env.example .env
```

Execute a case-insensitive search for "CHANGE_ME" and update each value:

- `GIDEON_ADMIN_EMAIL` and `GIDEON_ADMIN_PASSWORD`
- `GIDEON_S3_SECRET_KEY`
- `GIDEON_AUTH_SECRET_KEY`
- `POSTGRES_PASSWORD`

## Enable Telemetry (optional)

Edit these values in `.env`:

```bash
GIDEON_OTEL_ENABLED="true"
GIDEON_OTEL_EXPORTER="otlp"
```

## Enable Debugging (optional)

Edit these values in `.env`:

```bash
GIDEON_DEBUG="true"
GIDEON_LOG_LEVEL="DEBUG"
```

## Start Services with Persistent Volumes

Create persistent volumes for data durability:

```bash
docker volume create gideon-postgres-data
docker volume create gideon-qdrant-data
docker volume create gideon-ollama-models
```

Then start the stack:

```bash
docker compose -f infrastructure/docker-compose.yml --env-file .env up -d
```

## Verify Services

> **Note on localhost vs. 127.0.0.1:** When accessing services from Docker
> Desktop on Windows, use `http://127.0.0.1:...` instead of
> `http://localhost:...`. Some services (like MinIO) may reject `localhost`
> due to DNS resolution issues.

### Verify Database Connectivity

1. Use your pg administrative tool of choice (on Windows I recommend
   pgAdmin4) or on the container itself:

```bash
/ # psql -d gideon -U gideon -W
Password: 
psql (17.9)
Type "help" for help.

gideon=# 
gideon=# \dt
             List of relations
 Schema |       Name       | Type  | Owner  
--------+------------------+-------+--------
 public | alembic_version  | table | gideon
 public | chat_feedback    | table | gideon
 public | chat_queries     | table | gideon
 public | chat_sessions    | table | gideon
 public | documents        | table | gideon
 public | firms            | table | gideon
 public | matter_access    | table | gideon
 public | matters          | table | gideon
 public | refresh_tokens   | table | gideon
 public | task_submissions | table | gideon
 public | users            | table | gideon
(11 rows)
```

### Verify `Default Firm` created

```bash
gideon=# SELECT * FROM firms;
                  id                  |     name     |          created_at           
--------------------------------------+--------------+-------------------------------
 67cf9709-512d-4831-b510-44de269719bd | Default Firm | 2026-04-22 19:20:16.950292+00
(1 row)

```

### Verify S3 Object Storage

Browse to <http://127.0.0.1:9001> and log in with:

- Username: `GIDEON_S3_ACCESS_KEY` value from `.env` (default: `gideon`)
- Password: `GIDEON_S3_SECRET_KEY` value from `.env`

You should see a bucket called `gideon`.

### Verify Celery/Flower

Browse to: <http://127.0.0.1:5555/flower/workers>

Verify that the worker is online

### Verify Qdrant

Browse to: <http://127.0.0.1:6333/dashboard>

There should be an empty collection called Gideon

### Make sure Ollama is running

- When you browse to: <http://127.0.0.1:11434/>
  - You should see a message 

### Verify Grafana

- When you browse to:  <http://127.0.0.1:3001/>
  - You should see the Grafana UI

NOTE: If you did not enable Telemetry there will be nothing to look at in the UI.

### Verify Gideon API

Browse to <http://127.0.0.1:8000/health> and you should see a JSON response:

```json
{"status": "ok"}
```

### Run a Test Task

```powershell
uv run scripts/submit_task.py
```

- Verify that the task ran by looking at the Flower interface and checking logs in Grafana

## Authenticate and Run a Bulk Ingestion to the Global Knowledge Matter

```powershell
uv run gideon login --email $env:GIDEON_ADMIN_EMAIL --password $env:GIDEON_ADMIN_PASSWORD
uv run gideon document bulk-ingest "C:\Corpus\" --matter-id 00000000-0000-0000-0000-000000000001
```
