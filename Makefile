# ============================================================================
# Real Estate Agentic Platform — Makefile
# ============================================================================
# Usage: make <target>
# Run `make help` to see all available targets.
# ============================================================================

.DEFAULT_GOAL := help
SHELL := /bin/bash

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
PYTHON       ?= python
PIP          ?= pip
UVICORN_PORT ?= 8000
VITE_PORT    ?= 5173
COMPOSE_FILE ?= docker-compose.yml
SHARED_COMPOSE ?= ~/docker-shared-services.yml

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------
.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ============================================================================
# Setup
# ============================================================================
.PHONY: install install-backend install-frontend setup

install: install-backend install-frontend ## Install all dependencies

install-backend: ## Install Python dependencies (dev)
	$(PIP) install -e ".[dev]"

install-frontend: ## Install frontend dependencies
	cd frontend && npm install

setup: install db-init db-migrate db-seed ## Full first-time setup
	@echo "Setup complete. Run 'make dev' to start."

# ============================================================================
# Development servers
# ============================================================================
.PHONY: dev dev-backend dev-frontend

dev: ## Show how to start dev servers
	@echo "Run in separate terminals:"
	@echo "  make dev-backend"
	@echo "  make dev-frontend"

dev-backend: ## Start FastAPI dev server
	uvicorn main:app --reload --port $(UVICORN_PORT)

dev-frontend: ## Start Vite dev server
	cd frontend && npm run dev -- --port $(VITE_PORT)

# ============================================================================
# Docker
# ============================================================================
.PHONY: infra infra-down dev-docker docker-build docker-up docker-down

infra: ## Start shared infra (Postgres + Redis)
	docker compose -f $(SHARED_COMPOSE) up -d postgres redis

infra-down: ## Stop shared infra
	docker compose -f $(SHARED_COMPOSE) down

dev-docker: ## Start full stack via Docker Compose
	docker compose -f $(COMPOSE_FILE) up --build

docker-build: ## Build Docker images
	docker compose -f $(COMPOSE_FILE) build

docker-up: ## Start Docker Compose (detached)
	docker compose -f $(COMPOSE_FILE) up -d

docker-down: ## Stop Docker Compose
	docker compose -f $(COMPOSE_FILE) down

# ============================================================================
# Database
# ============================================================================
.PHONY: db-init db-migrate db-migrate-new db-seed db-seed-tokyo db-reset

db-init: ## Initialize shared database
	bash scripts/init-shared-db.sh

db-migrate: ## Run Alembic migrations to head
	alembic upgrade head

db-migrate-new: ## Create new migration (MSG="description")
	alembic revision --autogenerate -m "$(MSG)"

db-seed: ## Seed properties
	$(PYTHON) scripts/seed_properties.py

db-seed-tokyo: ## Seed Tokyo properties
	$(PYTHON) scripts/seed_tokyo.py

db-reset: db-init db-migrate db-seed ## Reset DB: init + migrate + seed

# ============================================================================
# Market signals
# ============================================================================
.PHONY: signals-backfill signals-fetch signals-list

signals-backfill: ## Backfill market signals from properties table
	$(PYTHON) scripts/backfill_market_signals.py

signals-fetch: ## Fetch external signals (SRC=mock)
	$(PYTHON) scripts/fetch_external_signals.py --source $(SRC)

signals-list: ## List registered signal providers
	$(PYTHON) scripts/fetch_external_signals.py --list

# ============================================================================
# Testing
# ============================================================================
.PHONY: test test-backend test-frontend test-e2e test-cov

test: test-backend test-frontend ## Run all tests

test-backend: ## Run Python tests
	pytest tests/ -v --tb=short

test-frontend: ## Run frontend unit tests
	cd frontend && npm run test -- --run

test-e2e: ## Run Playwright E2E tests
	cd frontend && npm run test:e2e

test-cov: ## Run backend tests with coverage
	pytest tests/ --cov=. --cov-report=term-missing --cov-report=html

# ============================================================================
# Code quality
# ============================================================================
.PHONY: lint lint-backend lint-frontend fmt typecheck check

lint: lint-backend lint-frontend ## Lint all code

lint-backend: ## Lint Python with ruff
	ruff check .

lint-frontend: ## TypeScript type check
	cd frontend && npx tsc --noEmit

fmt: ## Auto-format Python code
	ruff format .
	ruff check --fix .

typecheck: ## Run mypy
	mypy --ignore-missing-imports agent api db services intelligence middleware domain

check: lint typecheck test ## Full pre-commit check

# ============================================================================
# Auth
# ============================================================================
.PHONY: create-dev-user

create-dev-user: ## Create dev Supabase user
	$(PYTHON) scripts/create_dev_user.py

# ============================================================================
# Production
# ============================================================================
.PHONY: build prod

build: ## Build frontend for production
	cd frontend && npm run build

prod: ## Start production Docker stack
	docker compose -f docker-compose.prod.yml up -d

# ============================================================================
# Cleanup
# ============================================================================
.PHONY: clean clean-py clean-frontend

clean: clean-py clean-frontend ## Remove all build artifacts

clean-py: ## Remove Python caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage

clean-frontend: ## Remove frontend build artifacts
	rm -rf frontend/dist frontend/node_modules/.vite
