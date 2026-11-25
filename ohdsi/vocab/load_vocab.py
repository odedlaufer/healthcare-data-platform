"""Load an OHDSI Athena vocabulary release into the vocab schema (FR-CDM1).

The whole release loads in one transaction, so readers see either the old release or the
new one, never a mix. For speed, each table's indexes and primary key are dropped before
COPY and rebuilt afterwards from their own catalog definitions. Every table is checked
for exact row accounting: data lines in the file = rows in the table.

Usage:
    uv run python ohdsi/vocab/load_vocab.py data/vocab/<release>
"""

import argparse
import os
import sys
import time
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.rows import TupleRow

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "vocab"
CHUNK_BYTES = 8 * 1024 * 1024

# Athena files that have a CDM 5.4 table. CONCEPT_METADATA, CONCEPT_RELATIONSHIP_METADATA
# and PACK_CONTENT ship with Athena but are not part of CDM 5.4, so they are not loaded.
TABLES = (
    "domain",
    "vocabulary",
    "concept_class",
    "relationship",
    "concept",
    "concept_synonym",
    "concept_relationship",
    "concept_ancestor",
    "drug_strength",
)


def dsn() -> str:
    url = os.environ.get("HDP_DATABASE_URL")
    if url:
        return url
    password = (REPO_ROOT / "secrets" / "postgres_password").read_text().strip()
    return f"postgresql://hdp_admin:{password}@127.0.0.1:45432/healthcare"


def _drop_indexes(cur: psycopg.Cursor[TupleRow], table: str) -> list[str]:
    """Drop a table's indexes and primary key; return the statements that rebuild them."""
    cur.execute(
        """
        SELECT i.indexrelid::regclass::text, pg_get_indexdef(i.indexrelid),
               c.conname, pg_get_constraintdef(c.oid)
        FROM pg_index i
        LEFT JOIN pg_constraint c ON c.conindid = i.indexrelid AND c.contype = 'p'
        WHERE i.indrelid = %s::regclass
        """,
        (f"{SCHEMA}.{table}",),
    )
    rebuild: list[str] = []
    target = sql.Identifier(SCHEMA, table)
    for index_name, index_def, constraint_name, constraint_def in cur.fetchall():
        if constraint_name and constraint_def:
            cur.execute(
                sql.SQL("ALTER TABLE {} DROP CONSTRAINT {}").format(
                    target, sql.Identifier(constraint_name)
                )
            )
            rebuild.append(
                f"ALTER TABLE {SCHEMA}.{table} ADD CONSTRAINT {constraint_name} {constraint_def}"
            )
        else:
            cur.execute(sql.SQL("DROP INDEX {}").format(sql.SQL(index_name)))
            rebuild.append(index_def)
    return rebuild


def _copy(cur: psycopg.Cursor[TupleRow], path: Path) -> int:
    """Stream one tab-separated Athena file into its table; return the data lines sent."""
    table = path.stem.lower()
    with path.open("rb") as handle:
        columns = handle.readline().decode().strip().split("\t")
        statement = sql.SQL(
            "COPY {} ({}) FROM STDIN WITH (FORMAT csv, DELIMITER E'\\t', QUOTE E'\\b')"
        ).format(sql.Identifier(SCHEMA, table), sql.SQL(", ").join(map(sql.Identifier, columns)))
        lines = 0
        last = b"\n"
        with cur.copy(statement) as copy:
            while chunk := handle.read(CHUNK_BYTES):
                copy.write(chunk)
                lines += chunk.count(b"\n")
                last = chunk[-1:]
        return lines + (last != b"\n")


def load(release_dir: Path) -> int:
    missing = [t for t in TABLES if not (release_dir / f"{t.upper()}.csv").is_file()]
    if missing:
        print(f"missing files in {release_dir}: {', '.join(missing)}")
        return 1

    failures = 0
    with psycopg.connect(dsn()) as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL ROLE engineer")
        cur.execute("SET LOCAL maintenance_work_mem = '256MB'")
        print(f"{'table':<22}{'file rows':>14}{'table rows':>14}{'seconds':>10}")
        for table in TABLES:
            started = time.monotonic()
            rebuild = _drop_indexes(cur, table)
            cur.execute(sql.SQL("TRUNCATE {}").format(sql.Identifier(SCHEMA, table)))
            file_rows = _copy(cur, release_dir / f"{table.upper()}.csv")
            for statement in rebuild:
                cur.execute(sql.SQL(statement))
            cur.execute(sql.SQL("ANALYZE {}").format(sql.Identifier(SCHEMA, table)))
            cur.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(SCHEMA, table)))
            row = cur.fetchone()
            table_rows = int(row[0]) if row else -1
            failures += file_rows != table_rows
            flag = "" if file_rows == table_rows else "  MISMATCH"
            print(
                f"{table:<22}{file_rows:>14,}{table_rows:>14,}"
                f"{time.monotonic() - started:>10.1f}{flag}"
            )
        if failures:
            raise SystemExit(f"{failures} table(s) failed row accounting; nothing was committed")
        cur.execute("RESET ROLE")
    print(f"committed release {release_dir.name}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("release_dir", type=Path, help="directory with the extracted CSV files")
    return load(parser.parse_args().release_dir)


if __name__ == "__main__":
    sys.exit(main())
