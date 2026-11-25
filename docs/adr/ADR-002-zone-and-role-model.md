# ADR-002: Zone and role model

- Status: Accepted
- Date: 2026-11-25

## Context

Identified patient data must never reach analysts, every read of identified data must be
auditable, and the model must exist before any data does, so no step runs on an unprotected
design (PRD sections 5 and 7).

## Decision

**Zones are schemas in one `healthcare` database**, each with a comment describing it:
`raw_phi` and `mpi` (identified), `deid`, `cdm`, `vocab`, `results`, `marts`, `census`, `ops`,
`audit`, and `truth` (ground truth, used only for scoring).

**Roles are NOLOGIN groups** created by migration `20261124000002`; people and service accounts
get membership later.

| Role | Schema access | Table privileges on new tables |
| --- | --- | --- |
| engineer | owns every zone schema | owner |
| steward | raw_phi, mpi, deid, census | read; mpi also insert and update (match review queue) |
| analyst | deid, cdm, vocab, results, marts | read |
| researcher | vocab | read; suppressed views granted explicitly in Phase 6 |
| census_viewer | census | none; count views granted explicitly in Phase 5 |

- `engineer` owns all zone schemas, so default privileges grant access to every table the
  pipeline creates, with no ad-hoc grants (GOV-1).
- `PUBLIC` has no access to the database or the `public` schema.
- Where PRD section 5 and section 7.1 differ on researcher access to `cdm` and `results`, the
  stricter section 7.1 applies: no row-level person data for researchers.

**Auditing (GOV-4):** pgaudit logs role and DDL statements everywhere, with passwords redacted.
Object auditing uses the `pgaudit_auditor` role: it holds read and write on every `raw_phi` and
`mpi` table, so every such access is logged whoever runs it.

**Airflow** has its own `airflow` database and login role, with no access to `healthcare`.

## Consequences

- `tests/governance/test_permission_matrix.py` asserts this model against a live database on
  every change to `governance/` (CI workflow `governance`).
- Object-level rules that need the objects to exist come with those objects: the steward-only
  date-shift column on `deid.person_map` (Phase 3), census count views (Phase 5), researcher
  suppressed views, row-level security and masking views (Phase 6).
