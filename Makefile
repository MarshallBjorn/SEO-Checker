.PHONY: dev down logs shell test lint format migrate migration

COMPOSE = docker compose --env-file .env -f compose/docker-compose.dev.yml

dev:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

shell:
	$(COMPOSE) exec app bash

test:
	$(COMPOSE) exec app pytest

lint:
	$(COMPOSE) exec app ruff check app/ tests/

lint-fix:
	$(COMPOSE) exec app ruff check --fix app/ tests/

format:
	$(COMPOSE) exec app ruff format app/ tests/

migrate:
	$(COMPOSE) exec app alembic upgrade head

migration:
	@read -p "Migration name: " name; \
	$(COMPOSE) exec app alembic revision --autogenerate -m "$$name"
