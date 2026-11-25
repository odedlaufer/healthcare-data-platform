#!/bin/sh
# Create the local secrets that are missing (SEC-1). An existing secret is never overwritten,
# so running this again is always safe. Files are created owner-only (mode 600).
set -eu

DIR="${SECRETS_DIR:-secrets}"
mkdir -p "$DIR"
umask 077

hex() { openssl rand -hex "$1" | tr -d '\n'; }
fernet_key() { openssl rand -base64 32 | tr -d '\n' | tr '+/' '-_'; }
admin_passwords() { printf '{"admin": "%s"}' "$(openssl rand -hex 16)"; }

create() {
  name="$1"
  shift
  [ -f "$DIR/$name" ] && return 0
  "$@" > "$DIR/$name.tmp"
  mv "$DIR/$name.tmp" "$DIR/$name"
  echo "created $DIR/$name"
}

create postgres_password hex 32
create s3_access_key hex 16
create s3_secret_key hex 32
create airflow_db_password hex 32
create airflow_fernet_key fernet_key
create airflow_api_secret_key hex 32
create airflow_jwt_secret hex 32
create airflow_admin_passwords.json admin_passwords
