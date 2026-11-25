"""Airflow (FR-AF*): every component is healthy, the API requires authentication, and a DAG
runs end to end on the LocalExecutor."""

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.airflow

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_URL = os.environ.get("HDP_AIRFLOW_URL", "http://127.0.0.1:48080")
SMOKE_DAG = "hdp_smoke"
COMPONENTS = ("metadatabase", "scheduler", "triggerer", "dag_processor")


def _request(path: str, method: str = "GET", body: Any = None, token: str | None = None) -> Any:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(  # noqa: S310
        f"{BASE_URL}{path}", data=data, headers=headers, method=method
    )
    with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
        return json.loads(response.read() or b"null")


@pytest.fixture(scope="module")
def token() -> str:
    passwords = json.loads((REPO_ROOT / "secrets" / "airflow_admin_passwords.json").read_text())
    result = _request("/auth/token", "POST", {"username": "admin", "password": passwords["admin"]})
    return str(result["access_token"])


def test_all_components_healthy() -> None:
    health = _request("/api/v2/monitor/health")
    assert {name: health[name]["status"] for name in COMPONENTS} == dict.fromkeys(
        COMPONENTS, "healthy"
    )


def test_api_requires_authentication() -> None:
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        _request("/api/v2/dags")
    assert excinfo.value.code == 401


def test_wrong_password_is_rejected() -> None:
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        _request("/auth/token", "POST", {"username": "admin", "password": "wrong"})
    assert excinfo.value.code == 401


def test_dags_import_without_errors(token: str) -> None:
    assert _request("/api/v2/importErrors", token=token)["total_entries"] == 0
    dag_ids = {dag["dag_id"] for dag in _request("/api/v2/dags", token=token)["dags"]}
    assert SMOKE_DAG in dag_ids


def test_smoke_dag_runs_to_success(token: str) -> None:
    path = f"/api/v2/dags/{SMOKE_DAG}"
    _request(path, "PATCH", {"is_paused": False}, token)
    try:
        run = _request(f"{path}/dagRuns", "POST", {"logical_date": None}, token)
        run_path = f"{path}/dagRuns/{run['dag_run_id']}"
        deadline = time.monotonic() + 120
        state = run["state"]
        while state not in {"success", "failed"} and time.monotonic() < deadline:
            time.sleep(3)
            state = _request(run_path, token=token)["state"]
        assert state == "success"
    finally:
        _request(path, "PATCH", {"is_paused": True}, token)
