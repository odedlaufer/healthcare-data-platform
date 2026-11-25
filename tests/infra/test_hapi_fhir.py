"""Hospital A source system (FR-SRC2, FR-ING1): HAPI FHIR serves R4 over its own Postgres and
completes a FHIR Bulk Data $export end to end."""

import json
import os
import time
import urllib.parse
import urllib.request
import uuid
from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Any

import pytest

pytestmark = pytest.mark.fhir

BASE_URL = os.environ.get("HDP_FHIR_URL", "http://127.0.0.1:48090/fhir")
FHIR_JSON = "application/fhir+json"
TEST_SYSTEM = "urn:hdp:test"


def _call(
    url: str,
    method: str = "GET",
    body: Any = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], bytes]:
    request = urllib.request.Request(  # noqa: S310
        url,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Accept": FHIR_JSON, "Content-Type": FHIR_JSON, **(headers or {})},
        method=method,
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        response_headers = {key.lower(): value for key, value in response.headers.items()}
        return response.status, response_headers, response.read()


@pytest.fixture
def test_patient() -> Iterator[dict[str, Any]]:
    marker = str(uuid.uuid4())
    patient = {
        "resourceType": "Patient",
        "identifier": [{"system": TEST_SYSTEM, "value": marker}],
        "name": [{"family": "Probe", "given": ["Bulk"]}],
    }
    status, _, raw = _call(f"{BASE_URL}/Patient", "POST", patient)
    assert status == 201
    created: dict[str, Any] = json.loads(raw)
    yield created
    _call(f"{BASE_URL}/Patient/{created['id']}", "DELETE")


def test_capability_statement_is_r4_with_bulk_export() -> None:
    status, _, raw = _call(f"{BASE_URL}/metadata")
    capability = json.loads(raw)
    assert status == 200
    assert capability["fhirVersion"] == "4.0.1"
    operations = {
        operation["name"] for rest in capability["rest"] for operation in rest.get("operation", [])
    }
    assert "export" in operations


def test_bulk_export_returns_created_patient(test_patient: dict[str, Any]) -> None:
    updated = datetime.fromisoformat(test_patient["meta"]["lastUpdated"])
    since = (updated - timedelta(seconds=1)).isoformat()
    query = urllib.parse.urlencode({"_type": "Patient", "_since": since})
    status, headers, _ = _call(f"{BASE_URL}/$export?{query}", headers={"Prefer": "respond-async"})
    assert status == 202
    poll_url = headers["content-location"]

    deadline = time.monotonic() + 180
    while True:
        status, _, raw = _call(poll_url)
        if status == 200 or time.monotonic() > deadline:
            break
        time.sleep(3)
    assert status == 200

    manifest = json.loads(raw)
    lines: list[dict[str, Any]] = []
    for output in manifest["output"]:
        _, _, ndjson = _call(output["url"], headers={"Accept": "application/fhir+ndjson"})
        lines.extend(json.loads(line) for line in ndjson.decode().splitlines() if line)
    exported_ids = {resource["id"] for resource in lines}
    assert test_patient["id"] in exported_ids
