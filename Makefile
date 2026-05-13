.PHONY: dev down logs shell test lint format migrate migration

dev:
	docker compose -f compose/docker-compose.dev.yml up -d --build

down:
	docker compose -f compose/docker-compose.dev.yml down

logs:
	docker compose -f compose/docker-compose.dev.yml logs -f

shell:
	docker compose -f compose/docker-compose.dev.yml exec app bash

test:
	docker compose -f compose/docker-compose.dev.yml exec app pytest

lint:
	docker compose -f compose/docker-compose.dev.yml exec app ruff check app/ tests/

format:
	docker compose -f compose/docker-compose.dev.yml exec app ruff format app/ tests/

migrate:
	docker compose -f compose/docker-compose.dev.yml exec app alembic upgrade head

migration:
	@read -p "Migration name: " name; \
	docker compose -f compose/docker-compose.dev.yml exec app alembic revision --autogenerate -m "$$name"