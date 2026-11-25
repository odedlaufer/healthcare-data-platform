# ADR-006: SeaweedFS instead of MinIO for object storage

- Status: Accepted
- Date: 2026-11-25
- Supersedes: the MinIO choice in PRD section 2

## Context

The PRD names MinIO for the landing zone. The MinIO open-source project was archived upstream
on 2026-02-13: no further releases or security patches, and the official community images were
removed from Docker Hub. Building on an unmaintained component contradicts the production-grade
goal of the project.

## Decision

Use SeaweedFS (Apache 2.0, actively maintained, S3-compatible) as the object store, pinned by
digest (`chrislusf/seaweedfs:4.54`). It is the same store used in the Lichess and payments-fraud
projects, so operational knowledge carries over.

- One S3 identity, `pipeline`, scoped to the `landing` bucket (read, write, list, tagging).
  It cannot create buckets; buckets are created by `governance/storage/create_buckets.sh`.
- Credentials are Docker secrets, never environment variables or committed files (SEC-1).
- Only the S3 API is published, on `127.0.0.1:48333`; master and filer UIs stay internal.

## Consequences

- All landing-zone code uses the plain S3 API (boto3), so the store can be swapped later.
- The PRD's "MinIO" references read as "S3-compatible object store (SeaweedFS)".
- Retention (SEC-3) is implemented with SeaweedFS's S3 lifecycle support when the landing
  zone starts receiving data.
