"""Landing zone (PRD section 5): object storage is reachable only with the pipeline identity,
and that identity is scoped to the landing bucket."""

import os
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import boto3
import pytest
from botocore.config import Config
from botocore.exceptions import ClientError
from mypy_boto3_s3 import S3Client

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[2]
ENDPOINT = os.environ.get("HDP_S3_ENDPOINT", "http://127.0.0.1:48333")
BUCKET = "landing"


def _secret(name: str) -> str:
    return (REPO_ROOT / "secrets" / name).read_text().strip()


def _client(access_key: str, secret_key: str) -> S3Client:
    return boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="us-east-1",
        config=Config(s3={"addressing_style": "path"}, retries={"max_attempts": 1}),
    )


@pytest.fixture(scope="module")
def s3() -> S3Client:
    return _client(_secret("s3_access_key"), _secret("s3_secret_key"))


def test_pipeline_round_trip_in_landing(s3: S3Client) -> None:
    key = f"_probe/{uuid.uuid4()}.ndjson"
    body = b'{"resourceType":"Patient","id":"probe"}\n'
    s3.put_object(Bucket=BUCKET, Key=key, Body=body)
    try:
        assert s3.get_object(Bucket=BUCKET, Key=key)["Body"].read() == body
        listed = s3.list_objects_v2(Bucket=BUCKET, Prefix="_probe/").get("Contents", [])
        assert key in {obj.get("Key") for obj in listed}
    finally:
        s3.delete_object(Bucket=BUCKET, Key=key)


def test_pipeline_cannot_create_buckets(s3: S3Client) -> None:
    with pytest.raises(ClientError) as excinfo:
        s3.create_bucket(Bucket=f"probe-{uuid.uuid4().hex[:8]}")
    assert excinfo.value.response.get("Error", {}).get("Code") == "AccessDenied"


def test_wrong_secret_is_rejected() -> None:
    client = _client(_secret("s3_access_key"), "x" * 64)
    with pytest.raises(ClientError) as excinfo:
        client.list_objects_v2(Bucket=BUCKET)
    assert excinfo.value.response.get("Error", {}).get("Code") == "SignatureDoesNotMatch"


def test_anonymous_access_is_rejected() -> None:
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        urllib.request.urlopen(f"{ENDPOINT}/{BUCKET}/", timeout=5)  # noqa: S310
    assert excinfo.value.code == 403
