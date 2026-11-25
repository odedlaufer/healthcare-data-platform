#!/bin/sh
# SeaweedFS entrypoint: writes the S3 identity file from Docker secrets, then starts the server.
# The single identity is the pipeline service, scoped to the landing bucket (PRD section 5).
set -eu

SECRETS_DIR="${SECRETS_DIR:-/run/secrets}"
access_key="$(cat "$SECRETS_DIR/s3_access_key")"
secret_key="$(cat "$SECRETS_DIR/s3_secret_key")"

umask 077
cat > /tmp/s3.json <<JSON
{"identities":[{"name":"pipeline","credentials":[{"accessKey":"${access_key}","secretKey":"${secret_key}"}],"actions":["Read:landing","Write:landing","List:landing","Tagging:landing"]}]}
JSON

exec weed server -dir="${DATA_DIR:-/data}" -s3 -s3.port=8333 -s3.config=/tmp/s3.json \
  -master.telemetry=false \
  -s3.concurrentUploadLimitMB=64 \
  -filer.concurrentUploadLimitMB=64 \
  -volume.concurrentUploadLimitMB=64
