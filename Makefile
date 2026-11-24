SHELL := /bin/bash
.DEFAULT_GOAL := help

PACKAGES := sources ingest mpi deid adt

.PHONY: help install lint format typecheck test check

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install: ## Install locked dependencies and git hooks
	uv sync --locked
	GIT_CONFIG_GLOBAL=/dev/null uv run pre-commit install

lint: ## Lint and check formatting (ruff)
	uv run ruff check .
	uv run ruff format --check .

format: ## Auto-fix lint issues and format (ruff)
	uv run ruff check --fix .
	uv run ruff format .

typecheck: ## Type-check (mypy strict)
	uv run mypy $(PACKAGES) tests

test: ## Run tests with coverage (fails under 80%)
	uv run pytest $(addprefix --cov=,$(PACKAGES)) --cov-report=term-missing --cov-fail-under=80

check: lint typecheck test ## Run all checks (same as CI)
