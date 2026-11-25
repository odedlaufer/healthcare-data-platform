# ADR-001: Technology stack

- Status: Accepted
- Date: 2026-11-25

## Context

The platform must ingest FHIR, match patients, de-identify, and standardise into OMOP CDM 5.4 on
a 16 GB laptop with Docker Desktop, using only open-source tools. Shared foundations stay the
same as the earlier portfolio projects; every other layer is healthcare-specific (PRD section 2).

## Decision

| Layer | Choice | Version | Notes |
| --- | --- | --- | --- |
| Language and tooling | Python, uv, ruff, mypy (strict), pytest | Python 3.12 | 3.12 rather than 3.14 for Presidio, spaCy and Splink compatibility |
| Warehouse | PostgreSQL with pgaudit | 16.16, pgaudit 16.2 | Reference database for OHDSI tools; server package held so pgaudit cannot upgrade it |
| Migrations | dbmate | 2.37.0 | Plain SQL, reversible, same tool as the payments-fraud project |
| Object storage | SeaweedFS | 4.54 | See ADR-006 |
| OMOP DDL | OHDSI CommonDataModel | v5.4.3 | Vendored unchanged, rendered into a migration |
| Vocabularies | OHDSI Athena | v5.0 29-AUG-26 | Free vocabularies only (ADR-005) |
| Orchestration | Apache Airflow, LocalExecutor | 3.4.0 | No Celery or Redis; configured from Docker secrets |
| Source system | HAPI FHIR server | Phase 1 | FHIR R4 API and Bulk Data export |
| Processing | Polars | Phase 2 | Single-node flattening of nested FHIR JSON |
| Record linkage | Splink | Phase 3 | |
| De-identification | Microsoft Presidio, HMAC pseudonyms, date shifting | Phase 3 | |
| Transformations | dbt Core + dbt-postgres | Phase 4 | |
| Data quality | OHDSI DQD and Achilles, dbt tests | Phase 4 | Isolated R container (ADR-003) |
| Event transport | RabbitMQ Streams, MLLP listener | Phase 5 | ADR-004 |
| Catalog and lineage | OpenMetadata | Phase 6 | |
| BI | Metabase | Phase 6 | |

## Consequences

- Services join `docker-compose.yml` in the phase that first uses them, each in a profile
  (`core`, `airflow`, and later `fhir`, `stream`, `ohdsi`, `governance`, `bi`), so only what a
  phase needs runs at once.
- Every image is pinned to an exact version; images that cannot be pinned by tag are pinned by
  digest.
- Secrets are Docker secret files created by `make secrets`; no service reads a secret from an
  environment value (SEC-1).
