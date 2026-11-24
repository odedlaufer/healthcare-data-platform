"""Smoke test: every pipeline package is importable and documented."""

import importlib

import pytest

PACKAGES = ["sources", "ingest", "mpi", "deid", "adt"]


@pytest.mark.parametrize("name", PACKAGES)
def test_package_imports(name: str) -> None:
    module = importlib.import_module(name)
    assert module.__doc__
