-- Creates additional databases alongside the app database.
-- Runs automatically on first container startup via docker-entrypoint-initdb.d.
-- The default POSTGRES_DB (gideon) is created by the postgres image itself.

\c postgres

-- Celery task result persistence (separate DB for fault isolation)
CREATE DATABASE gideon_tasks;
GRANT ALL PRIVILEGES ON DATABASE gideon_tasks TO gideon;

-- Test databases (pytest-docker stack)
CREATE DATABASE gideon_test;
GRANT ALL PRIVILEGES ON DATABASE gideon_test TO gideon;

CREATE DATABASE gideon_tasks_test;
GRANT ALL PRIVILEGES ON DATABASE gideon_tasks_test TO gideon;
