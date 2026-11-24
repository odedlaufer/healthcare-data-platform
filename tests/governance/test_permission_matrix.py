"""GOV-1: the live role and grant model matches the permission matrix in PRD section 7.1."""

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any, LiteralString

import psycopg
import pytest
from psycopg import errors, sql
from psycopg.rows import TupleRow

pytestmark = pytest.mark.integration

Conn = psycopg.Connection[TupleRow]

REPO_ROOT = Path(__file__).resolve().parents[2]

ZONE_SCHEMAS = (
    "raw_phi",
    "mpi",
    "deid",
    "cdm",
    "vocab",
    "results",
    "marts",
    "census",
    "ops",
    "audit",
    "truth",
)
PRIVILEGES = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE")
READ = frozenset({"SELECT"})
READ_WRITE = frozenset({"SELECT", "INSERT", "UPDATE", "DELETE"})

# Which schemas each role can enter (section 7.1).
SCHEMA_USAGE: dict[str, set[str]] = {
    "steward": {"raw_phi", "mpi", "deid", "census"},
    "analyst": {"deid", "cdm", "vocab", "results", "marts"},
    "researcher": {"vocab"},
    "census_viewer": {"census"},
}

# Privileges each role gets on new engineer-owned tables (section 7.1, GOV-4).
TABLE_PRIVILEGES: dict[str, dict[str, frozenset[str]]] = {
    "steward": {
        "raw_phi": READ,
        "mpi": frozenset({"SELECT", "INSERT", "UPDATE"}),
        "deid": READ,
        "census": READ,
    },
    "analyst": dict.fromkeys(("deid", "cdm", "vocab", "results", "marts"), READ),
    "researcher": {"vocab": READ},
    "census_viewer": {},
    "pgaudit_auditor": dict.fromkeys(("raw_phi", "mpi"), READ_WRITE),
}


def _dsn() -> str:
    url = os.environ.get("HDP_DATABASE_URL")
    if url:
        return url
    password = (REPO_ROOT / "secrets" / "postgres_password").read_text().strip()
    return f"postgresql://hdp_admin:{password}@127.0.0.1:45432/healthcare"


def _scalar(conn: Conn, query: LiteralString, params: tuple[Any, ...] = ()) -> Any:
    row = conn.execute(query, params).fetchone()
    assert row is not None
    return row[0]


@pytest.fixture(scope="module")
def conn() -> Iterator[Conn]:
    with psycopg.connect(_dsn(), autocommit=True) as connection:
        yield connection


@pytest.fixture
def probe_tables(conn: Conn) -> Iterator[None]:
    """Create one table per zone schema as engineer; everything is rolled back afterwards."""
    with conn.transaction(force_rollback=True):
        conn.execute("SET LOCAL ROLE engineer")
        for schema in ZONE_SCHEMAS:
            conn.execute(
                sql.SQL("CREATE TABLE {}.gov_probe (id int)").format(sql.Identifier(schema))
            )
        conn.execute("RESET ROLE")
        yield


def test_engineer_owns_every_zone_schema(conn: Conn) -> None:
    rows = conn.execute(
        "SELECT nspname, pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname = ANY(%s)",
        (list(ZONE_SCHEMAS),),
    ).fetchall()
    assert dict(rows) == dict.fromkeys(ZONE_SCHEMAS, "engineer")


@pytest.mark.parametrize("role", sorted(SCHEMA_USAGE))
def test_schema_usage(conn: Conn, role: str) -> None:
    granted = {
        schema
        for schema in (*ZONE_SCHEMAS, "public")
        if _scalar(conn, "SELECT has_schema_privilege(%s, %s, 'USAGE')", (role, schema))
    }
    assert granted == SCHEMA_USAGE[role]


@pytest.mark.parametrize("role", sorted(TABLE_PRIVILEGES))
@pytest.mark.usefixtures("probe_tables")
def test_default_table_privileges(conn: Conn, role: str) -> None:
    granted: dict[str, frozenset[str]] = {}
    for schema in ZONE_SCHEMAS:
        privileges = frozenset(
            privilege
            for privilege in PRIVILEGES
            if _scalar(
                conn,
                "SELECT has_table_privilege(%s, %s, %s)",
                (role, f"{schema}.gov_probe", privilege),
            )
        )
        if privileges:
            granted[schema] = privileges
    assert granted == TABLE_PRIVILEGES[role]


@pytest.mark.usefixtures("probe_tables")
def test_analyst_is_denied_raw_phi(conn: Conn) -> None:
    with pytest.raises(errors.InsufficientPrivilege), conn.transaction():
        conn.execute("SET LOCAL ROLE analyst")
        conn.execute("SELECT * FROM raw_phi.gov_probe")


@pytest.mark.usefixtures("probe_tables")
def test_steward_can_read_raw_phi(conn: Conn) -> None:
    with conn.transaction():
        conn.execute("SET LOCAL ROLE steward")
        assert conn.execute("SELECT count(*) FROM raw_phi.gov_probe").fetchall() == [(0,)]


def test_public_has_no_database_access(conn: Conn) -> None:
    locked = _scalar(
        conn,
        """
        SELECT d.datacl IS NOT NULL
           AND NOT EXISTS (SELECT 1 FROM aclexplode(d.datacl) a WHERE a.grantee = 0)
        FROM pg_database d
        WHERE d.datname = current_database()
        """,
    )
    assert locked is True


def test_pgaudit_object_audit_role(conn: Conn) -> None:
    assert _scalar(conn, "SELECT current_setting('pgaudit.role')") == "pgaudit_auditor"


def test_omop_cdm_tables_owned_by_engineer(conn: Conn) -> None:
    rows = conn.execute(
        """
        SELECT schemaname, count(*), array_agg(DISTINCT tableowner)
        FROM pg_tables
        WHERE schemaname IN ('cdm', 'vocab')
        GROUP BY schemaname
        """
    ).fetchall()
    assert {schema: (count, owners) for schema, count, owners in rows} == {
        "cdm": (29, ["engineer"]),
        "vocab": (10, ["engineer"]),
    }


@pytest.mark.parametrize(
    ("role", "table", "allowed"),
    [
        ("analyst", "cdm.person", True),
        ("analyst", "vocab.concept", True),
        ("researcher", "vocab.concept", True),
        ("researcher", "cdm.person", False),
        ("steward", "cdm.person", False),
        ("census_viewer", "vocab.concept", False),
    ],
)
def test_omop_cdm_read_access(conn: Conn, role: str, table: str, allowed: bool) -> None:
    assert _scalar(conn, "SELECT has_table_privilege(%s, %s, 'SELECT')", (role, table)) is allowed
