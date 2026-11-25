#!/bin/sh
# Create the object-storage buckets if they are missing. Safe to run any number of times.
# Runs inside the seaweedfs container: docker compose exec -T seaweedfs sh /opt/hdp/create_buckets.sh
set -eu

BUCKETS="landing"
MASTER="${WEED_MASTER:-127.0.0.1:9333}"

list_buckets() {
  echo "s3.bucket.list" | weed shell -master="$MASTER" 2>/dev/null | awk '{print $1}'
}

existing="$(list_buckets)"
for bucket in $BUCKETS; do
  if printf '%s\n' "$existing" | grep -qx "$bucket"; then
    echo "bucket $bucket exists"
  else
    echo "s3.bucket.create -name $bucket" | weed shell -master="$MASTER" >/dev/null 2>&1
    echo "bucket $bucket created"
  fi
done

existing="$(list_buckets)"
for bucket in $BUCKETS; do
  printf '%s\n' "$existing" | grep -qx "$bucket" || { echo "bucket $bucket is missing" >&2; exit 1; }
done
