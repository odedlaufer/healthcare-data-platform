#!/bin/sh
# Create the Airflow metadata database and its login role. Safe to run any number of times;
# re-running also applies a rotated password. The password is read from a Docker secret by psql
# itself, so it never appears in a command line; pgaudit redacts it in the audit log.
set -eu

SECRETS_DIR="${SECRETS_DIR:-/run/secrets}"
PGHOST="${PGHOST:-postgres}"
PGUSER="${PGUSER:-hdp_admin}"
PGDATABASE="${PGDATABASE:-healthcare}"
PGPASSWORD="$(cat "$SECRETS_DIR/postgres_password")"
export PGHOST PGUSER PGDATABASE PGPASSWORD

psql -v ON_ERROR_STOP=1 -q -v secret_file="$SECRETS_DIR/airflow_db_password" <<'SQL'
\set pw `cat :secret_file`
SELECT format('CREATE ROLE airflow LOGIN PASSWORD %L', :'pw')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'airflow') \gexec
ALTER ROLE airflow LOGIN PASSWORD :'pw';
COMMENT ON ROLE airflow IS 'Owner of the Airflow metadata database; no access to the healthcare database.';
SELECT 'CREATE DATABASE airflow OWNER airflow'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'airflow') \gexec
REVOKE ALL ON DATABASE airflow FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE airflow TO airflow;
SQL

echo "airflow metadata database ready"
