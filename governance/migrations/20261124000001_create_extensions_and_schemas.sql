-- migrate:up
CREATE EXTENSION IF NOT EXISTS pgaudit;

CREATE SCHEMA raw_phi;
COMMENT ON SCHEMA raw_phi IS 'Identified zone: flattened FHIR, Clinic B, parsed ADT. Steward only, every query audited.';

CREATE SCHEMA mpi;
COMMENT ON SCHEMA mpi IS 'Identified zone: master patient index (golden_person, person_links). Steward only, audited.';

CREATE SCHEMA deid;
COMMENT ON SCHEMA deid IS 'De-identified zone: pseudonymised, date-shifted, generalised. Analyst read.';

CREATE SCHEMA cdm;
COMMENT ON SCHEMA cdm IS 'OMOP CDM 5.4 standard tables. Analyst and researcher read.';

CREATE SCHEMA vocab;
COMMENT ON SCHEMA vocab IS 'OMOP standardised vocabularies from OHDSI Athena (free vocabularies only).';

CREATE SCHEMA results;
COMMENT ON SCHEMA results IS 'OHDSI Data Quality Dashboard and Achilles results.';

CREATE SCHEMA marts;
COMMENT ON SCHEMA marts IS 'Clinical analytics marts; researcher access via small-cell-suppressed views.';

CREATE SCHEMA census;
COMMENT ON SCHEMA census IS 'Real-time bed census from HL7v2 ADT. Counts only outside the steward role.';

CREATE SCHEMA ops;
COMMENT ON SCHEMA ops IS 'Pipeline operations: run metrics, resource accounting, DQ and PHI scan results.';

CREATE SCHEMA audit;
COMMENT ON SCHEMA audit IS 'pgaudit events loaded daily for the governance dashboard.';

CREATE SCHEMA truth;
COMMENT ON SCHEMA truth IS 'Ground truth for scoring only (patient links, ADT census, injected PHI). Never read by the pipeline.';

-- migrate:down
DROP SCHEMA truth, audit, ops, census, marts, results, vocab, cdm, deid, mpi, raw_phi CASCADE;
DROP EXTENSION IF EXISTS pgaudit;
