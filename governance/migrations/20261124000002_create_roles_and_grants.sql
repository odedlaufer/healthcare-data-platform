-- migrate:up

-- Group roles (NOLOGIN). Login users and service accounts are granted membership later.
CREATE ROLE engineer NOLOGIN;
COMMENT ON ROLE engineer IS 'Pipeline service: owns all zone schemas and their objects; writes everywhere.';
CREATE ROLE steward NOLOGIN;
COMMENT ON ROLE steward IS 'Data steward: reads identified data (raw_phi, mpi, deid, census), reviews match queue. Audited.';
CREATE ROLE analyst NOLOGIN;
COMMENT ON ROLE analyst IS 'Analyst: reads de-identified and OMOP data; never identified zones.';
CREATE ROLE researcher NOLOGIN;
COMMENT ON ROLE researcher IS 'Researcher: vocabularies and small-cell-suppressed views only; no row-level person data.';
CREATE ROLE census_viewer NOLOGIN;
COMMENT ON ROLE census_viewer IS 'Operations: census counts only; never person_key.';
CREATE ROLE pgaudit_auditor NOLOGIN;
COMMENT ON ROLE pgaudit_auditor IS 'pgaudit object-audit role: privileges granted to it are what gets logged (GOV-4).';

-- Lock down the database and the public schema.
DO $$
BEGIN
  EXECUTE format('REVOKE ALL ON DATABASE %I FROM PUBLIC', current_database());
  EXECUTE format('GRANT CONNECT ON DATABASE %I TO engineer, steward, analyst, researcher, census_viewer',
                 current_database());
  EXECUTE format('ALTER DATABASE %I SET pgaudit.role = %L', current_database(), 'pgaudit_auditor');
END
$$;
REVOKE ALL ON SCHEMA public FROM PUBLIC;

-- engineer owns every zone schema.
ALTER SCHEMA raw_phi OWNER TO engineer;
ALTER SCHEMA mpi     OWNER TO engineer;
ALTER SCHEMA deid    OWNER TO engineer;
ALTER SCHEMA cdm     OWNER TO engineer;
ALTER SCHEMA vocab   OWNER TO engineer;
ALTER SCHEMA results OWNER TO engineer;
ALTER SCHEMA marts   OWNER TO engineer;
ALTER SCHEMA census  OWNER TO engineer;
ALTER SCHEMA ops     OWNER TO engineer;
ALTER SCHEMA audit   OWNER TO engineer;
ALTER SCHEMA truth   OWNER TO engineer;

ALTER DEFAULT PRIVILEGES FOR ROLE engineer REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;

-- steward: identified zones. Write on mpi for the match review queue.
GRANT USAGE ON SCHEMA raw_phi, mpi, deid, census TO steward;
ALTER DEFAULT PRIVILEGES FOR ROLE engineer IN SCHEMA raw_phi, deid, census
  GRANT SELECT ON TABLES TO steward;
ALTER DEFAULT PRIVILEGES FOR ROLE engineer IN SCHEMA mpi
  GRANT SELECT, INSERT, UPDATE ON TABLES TO steward;

-- analyst: de-identified and OMOP zones. deid.person_map is revoked when it is created (Phase 3).
GRANT USAGE ON SCHEMA deid, cdm, vocab, results, marts TO analyst;
ALTER DEFAULT PRIVILEGES FOR ROLE engineer IN SCHEMA deid, cdm, vocab, results, marts
  GRANT SELECT ON TABLES TO analyst;

-- researcher: vocabularies only; suppressed views are granted explicitly (Phase 6).
GRANT USAGE ON SCHEMA vocab TO researcher;
ALTER DEFAULT PRIVILEGES FOR ROLE engineer IN SCHEMA vocab
  GRANT SELECT ON TABLES TO researcher;

-- census_viewer: schema usage only; count views are granted explicitly (Phase 5).
GRANT USAGE ON SCHEMA census TO census_viewer;

-- pgaudit object auditing: every read and write on identified tables is logged.
ALTER DEFAULT PRIVILEGES FOR ROLE engineer IN SCHEMA raw_phi, mpi
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO pgaudit_auditor;

-- migrate:down
DO $$
BEGIN
  EXECUTE format('ALTER DATABASE %I RESET pgaudit.role', current_database());
  EXECUTE format('GRANT CONNECT, TEMPORARY ON DATABASE %I TO PUBLIC', current_database());
END
$$;
GRANT USAGE ON SCHEMA public TO PUBLIC;
REASSIGN OWNED BY engineer TO CURRENT_USER;
-- One role per statement: a multi-role DROP OWNED fails on shared default ACL entries.
DROP OWNED BY steward;
DROP OWNED BY analyst;
DROP OWNED BY researcher;
DROP OWNED BY census_viewer;
DROP OWNED BY pgaudit_auditor;
DROP OWNED BY engineer;
DROP ROLE engineer, steward, analyst, researcher, census_viewer, pgaudit_auditor;
