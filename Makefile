SHELL := /bin/bash
.DEFAULT_GOAL := help

PACKAGES := sources ingest mpi deid adt
COMPOSE := docker compose --profile core --profile airflow --profile fhir
VOCAB_DIR ?= data/vocab/v5.0_2026-08-29
AIRFLOW_SERVICES := airflow-apiserver airflow-scheduler airflow-dag-processor airflow-triggerer
export AIRFLOW_UID ?= $(shell id -u)

.PHONY: help install secrets up airflow-up fhir-up down migrate psql vocab lint format typecheck test test-integration test-airflow test-fhir check

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Install locked dependencies and git hooks
	uv sync --locked
	GIT_CONFIG_GLOBAL=/dev/null uv run pre-commit install

secrets: ## Create local secrets if missing (never committed)
	@sh governance/create_secrets.sh

up: secrets ## Start the core stack, create buckets and apply migrations
	$(COMPOSE) up -d --build --wait postgres seaweedfs
	$(COMPOSE) exec -T seaweedfs sh /opt/hdp/create_buckets.sh
	$(COMPOSE) run --rm migrate up
	$(COMPOSE) run --rm airflow-db-init

airflow-up: up ## Start Airflow on top of the core stack
	$(COMPOSE) run --rm airflow-init
	$(COMPOSE) up -d --wait $(AIRFLOW_SERVICES)

fhir-up: secrets ## Start the HAPI FHIR source system (Hospital A EHR)
	$(COMPOSE) up -d --build --wait hapi-db hapi

down: ## Stop every service (data volumes are kept)
	$(COMPOSE) down

migrate: ## Apply pending migrations
	$(COMPOSE) run --rm migrate up

psql: ## Open psql as admin
	$(COMPOSE) exec postgres sh -c 'PGPASSWORD="$$(cat /run/secrets/postgres_password)" exec psql -U hdp_admin -d healthcare'

vocab: ## Load Athena vocabularies (VOCAB_DIR=data/vocab/<release>)
	uv run python ohdsi/vocab/load_vocab.py $(VOCAB_DIR)

lint: ## Lint and check formatting (ruff)
	uv run ruff check .
	uv run ruff format --check .
	uv run python ohdsi/ddl/render_migration.py --check

format: ## Auto-fix lint issues and format (ruff)
	uv run ruff check --fix .
	uv run ruff format .

typecheck: ## Type-check (mypy strict)
	uv run mypy $(PACKAGES) tests ohdsi

test: ## Run unit tests with coverage (fails under 80%)
	uv run pytest -m "not integration and not airflow and not fhir" $(addprefix --cov=,$(PACKAGES)) --cov-report=term-missing --cov-fail-under=80

test-integration: ## Run integration tests (needs: make up)
	uv run pytest -m integration

test-airflow: ## Run Airflow tests (needs: make airflow-up)
	uv run pytest -m airflow

test-fhir: ## Run HAPI FHIR tests (needs: make fhir-up)
	uv run pytest -m fhir

check: lint typecheck test ## Run all checks (same as CI)
