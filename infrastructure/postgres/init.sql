-- Creates additional databases alongside the app database.
-- Runs automatically on first container startup via docker-entrypoint-initdb.d.
-- The default POSTGRES_DB (opencase) is created by the postgres image itself.

\c postgres

-- Celery task result persistence (separate DB for fault isolation)
CREATE DATABASE opencase_tasks;
GRANT ALL PRIVILEGES ON DATABASE opencase_tasks TO opencase;

-- Test databases (pytest-docker stack)
CREATE DATABASE opencase_test;
GRANT ALL PRIVILEGES ON DATABASE opencase_test TO opencase;

CREATE DATABASE opencase_tasks_test;
GRANT ALL PRIVILEGES ON DATABASE opencase_tasks_test TO opencase;
