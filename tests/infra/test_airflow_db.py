"""Airflow metadata database: its own database and login role, isolated from healthcare data."""

import os
from pathlib import Path

import psycopg
import pytest

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[2]
HOST = os.environ.get("HDP_PG_HOST", "127.0.0.1")
PORT = os.environ.get("HDP_PG_PORT", "45432")


def _connect(database: str) -> psycopg.Connection[tuple[object, ...]]:
    password = (REPO_ROOT / "secrets" / "airflow_db_password").read_text().strip()
    return psycopg.connect(
        host=HOST, port=PORT, user="airflow", password=password, dbname=database, autocommit=True
    )


def test_airflow_owns_its_database() -> None:
    with _connect("airflow") as conn:
        row = conn.execute(
            "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = current_database()"
        ).fetchone()
        assert row == ("airflow",)
        with conn.transaction(force_rollback=True):
            conn.execute("CREATE TABLE airflow_probe (id int)")


def test_airflow_cannot_connect_to_healthcare() -> None:
    with pytest.raises(psycopg.OperationalError, match="CONNECT privilege"):
        _connect("healthcare")
