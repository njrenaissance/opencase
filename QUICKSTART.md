# Persistent Environment Setup

For setting up a persistent Gideon instance to ingest and work with
documents (not for testing).

## Update Environment Variables

Copy `.env.example` to `.env` and update required values:

```bash
cp .env.example .env
```

Execute a case-insensitive search for "CHANGE_ME" and update each value:

- `GIDEON_ADMIN_EMAIL` and `GIDEON_ADMIN_PASSWORD`
- `GIDEON_S3_SECRET_KEY`
- `GIDEON_JWT_SECRET`
- `POSTGRES_PASSWORD`

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

You will have to browse to http://127.0.0.1:9001 (localhost will not work because while it resolves to the correct address MinIO will not respond to that URL)

login with the values from the .env file that you updated
GIDEON_S3_ACCESS_KEY="gideon"
GIDEON_S3_SECRET_KEY=??

When you log in you should see a bucket called Gideon

### Verify Celery/Flower

Browse to: http://127.0.0.1:5555/flower/workers

Verify that the worker is online

### Verify Qdrant

Browe to: http://127.0.0.1:6333/dashboard

There should be an empty collection called Gideon


### Make sure Ollama is running

Browse to: http://127.0.0.1:11434/









### Verify Grafana
Browse to:  http://127.0.0.1:3001/ (no password required)




Browse to:  http://127.0.0.1:8000/health

## Run a Test Task

```powershell
uv run scripts/submit_task.py
```
Verify that the task ran by looking at the Flower interface
and checking logs in Grafana





## Authenticate and Run a Bulk Ingestion to the Global Knowledge Matter


```powershell
uv run gideon login --email $env:GIDEON_ADMIN_EMAIL --password $env:GIDEON_ADMIN_PASSWORD
uv run gideon document bulk-ingest "C:\Corpus\" --matter-id 00000000-0000-0000-0000-000000000001
```






# NOTES

* Make sure everything uses 127.0.0.1; localhost may not resolve properly inside of containers
* Should I make a Kubernetes operator for this?


## Change defaults in .env

Needs to be updated .env.example


GIDEON_CHUNKING_CHUNK_SIZE="3000"
GIDEON_CHUNKING_CHUNK_OVERLAP="600"
GIDEON_OTEL_ENABLED="true"
GIDEON_OTEL_EXPORTER="otlp"
GIDEON_OTEL_ENDPOINT="http://grafana:4318"
GIDEON_OTEL_SERVICE_NAME="gideon-api"
GIDEON_OTEL_SAMPLE_RATE="1.0"


FOR DEBUGGING PURPOSES you may want to:

### May Need to change these values for debugging

GIDEON_DEBUG="true"
GIDEON_LOG_LEVEL="DEBUG"


scripts should not contain: (me-specific files)
backfill_chunk_text.py
extract_zips.py
query_users.py ?  really  not that important
need to remove seed_demo.py as well

