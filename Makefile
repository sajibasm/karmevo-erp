API_PORT ?= 8010

.PHONY: dev-up dev-down migrate provision-demo test lint api

dev-up:
	docker compose -f deploy/compose.dev.yml up -d --wait

dev-down:
	docker compose -f deploy/compose.dev.yml down

migrate:
	cd backend && uv run alembic -n registry upgrade head && uv run python -m erp.cli upgrade-tenants

provision-demo:
	cd backend && uv run python -m erp.cli provision-tenant --account-number 100001 --name "Demo Traders"

test:
	cd backend && uv run pytest

lint:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run lint-imports

api:
	cd backend && uv run uvicorn --factory erp.main:ProductionApp.build --reload --port $(API_PORT)
