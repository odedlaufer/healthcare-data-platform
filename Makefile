SHELL := /bin/bash
.DEFAULT_GOAL := help

PACKAGES := sources ingest mpi deid adt
COMPOSE := docker compose --profile core

.PHONY: help install secrets up down migrate psql lint format typecheck test test-integration check

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Install locked dependencies and git hooks
	uv sync --locked
	GIT_CONFIG_GLOBAL=/dev/null uv run pre-commit install

secrets: ## Create local secrets if missing (never committed)
	@mkdir -p secrets
	@test -f secrets/postgres_password || { openssl rand -hex 32 > secrets/postgres_password && chmod 600 secrets/postgres_password && echo "created secrets/postgres_password"; }

up: secrets ## Start the core stack and apply migrations
	$(COMPOSE) up -d --build --wait postgres
	$(COMPOSE) run --rm migrate up

down: ## Stop the stack (data volumes are kept)
	$(COMPOSE) down

migrate: ## Apply pending migrations
	$(COMPOSE) run --rm migrate up

psql: ## Open psql as admin
	$(COMPOSE) exec postgres sh -c 'PGPASSWORD="$$(cat /run/secrets/postgres_password)" exec psql -U hdp_admin -d healthcare'

lint: ## Lint and check formatting (ruff)
	uv run ruff check .
	uv run ruff format --check .

format: ## Auto-fix lint issues and format (ruff)
	uv run ruff check --fix .
	uv run ruff format .

typecheck: ## Type-check (mypy strict)
	uv run mypy $(PACKAGES) tests

test: ## Run unit tests with coverage (fails under 80%)
	uv run pytest -m "not integration" $(addprefix --cov=,$(PACKAGES)) --cov-report=term-missing --cov-fail-under=80

test-integration: ## Run integration tests (needs: make up)
	uv run pytest -m integration

check: lint typecheck test ## Run all checks (same as CI)
