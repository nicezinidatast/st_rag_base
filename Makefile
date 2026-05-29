.PHONY: install lock dev lint type test up down migrate

# 의존성 동기화 (uv.lock 기준으로 .venv 구성. 없으면 생성)
install:
	uv sync

# 잠금파일만 갱신 (pyproject 변경 후)
lock:
	uv lock

dev:
	uv run uvicorn app.main:app --reload

lint:
	uv run ruff check .

type:
	uv run mypy app

test:
	uv run pytest

up:
	docker compose up -d

down:
	docker compose down

migrate:
	uv run alembic upgrade head
