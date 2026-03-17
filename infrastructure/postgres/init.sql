-- Creates the test database alongside the app database.
-- Runs automatically on first container startup via docker-entrypoint-initdb.d.
-- The default POSTGRES_DB (opencase) is created by the postgres image itself.

\c postgres

CREATE DATABASE opencase_test;

GRANT ALL PRIVILEGES ON DATABASE opencase_test TO opencase;
