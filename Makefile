# Common tasks. Run `make help` for the list.
SHELL := /bin/bash
COMPOSE := docker compose
BACKEND := $(COMPOSE) run --rm --no-deps backend
PY := backend/.venv/bin/python

.PHONY: help up down logs seed test test-backend test-frontend lint typecheck migrations-lint \
        e2e screenshots frontend-build lock image deploy-test fmt

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[1m%-16s\033[0m %s\n", $$1, $$2}'

up: ## Start the whole app (http://localhost:5173)
	$(COMPOSE) up --build -d
	@echo "App: http://localhost:5173   API: http://localhost:8000   MinIO: http://localhost:9001"

down: ## Stop everything (data is kept)
	$(COMPOSE) down

logs: ## Follow logs
	$(COMPOSE) logs -f --tail=100

seed: ## Load demo users (password Forklift-Demo-2026!)
	$(COMPOSE) exec backend python manage.py seed_dev

test: test-backend test-frontend ## All unit and integration tests

test-backend: ## pytest (needs `make up` for Postgres)
	$(COMPOSE) exec -e DJANGO_SETTINGS_MODULE=config.settings.test backend pytest

test-frontend: ## Vitest
	cd frontend && npx vitest run

lint: ## Ruff, ESLint, ShellCheck, terraform fmt
	$(COMPOSE) exec backend ruff check . && $(COMPOSE) exec backend ruff format --check .
	cd frontend && npm run lint
	shellcheck -x infra/deploy/*.sh infra/cloud-init/deploy-entry.sh infra/scripts/*.sh backend/docker-entrypoint.sh
	terraform fmt -check -recursive infra/terraform

typecheck: ## mypy (strict) and tsc (strict)
	$(COMPOSE) exec backend mypy .
	cd frontend && npm run typecheck

migrations-lint: ## Migrations complete and safe (expand/contract)
	$(COMPOSE) exec -e DJANGO_SETTINGS_MODULE=config.settings.test backend sh -c \
	  "python manage.py makemigrations --check --dry-run && python manage.py lintmigrations --warnings-as-errors --exclude-migration-tests"

frontend-build: ## Build the React app into backend/frontend_dist
	cd frontend && npm run build

e2e: frontend-build ## Playwright end-to-end tests against a production-like server
	./infra/scripts/run-e2e.sh e2e

screenshots: frontend-build ## Phase screenshots into docs/screenshots/phase-N
	./infra/scripts/run-e2e.sh screenshots

image: ## Build the production image locally
	docker build --target runtime -t mmh-app:local .

deploy-test: image ## Run the real blue/green deploy scripts locally
	./infra/scripts/test-deploy-local.sh mmh-app:local

lock: ## Re-pin Python dependencies with hashes
	cd backend && uv pip compile --python-version 3.12 --python-platform x86_64-manylinux_2_28 --generate-hashes -q requirements/base.in -o requirements/base.txt
	cd backend && uv pip compile --python-version 3.12 --python-platform x86_64-manylinux_2_28 --generate-hashes -q requirements/dev.in -o requirements/dev.txt
