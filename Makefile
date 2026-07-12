SHELL := /bin/zsh
PY := backend/.venv/bin/python
PNPM_HOME ?= $(HOME)/Library/pnpm
PNPM := $(PNPM_HOME)/pnpm

.PHONY: up install migrate seed api web check eval demo-reset

up:
	docker compose up -d --wait

install:
	python3.12 -m venv backend/.venv
	backend/.venv/bin/pip install --upgrade pip -q
	backend/.venv/bin/pip install -r backend/requirements.txt
	cd frontend && $(PNPM) install

migrate:
	cd backend && .venv/bin/alembic upgrade head

seed:
	cd backend && .venv/bin/python -m scripts.seed

api:
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

web:
	cd frontend && $(PNPM) dev

check:
	cd backend && .venv/bin/pytest -q tests && .venv/bin/python -m scripts.smoke

eval:
	cd backend && .venv/bin/python -m scripts.evaluate

demo-reset:
	cd backend && .venv/bin/alembic downgrade base && .venv/bin/alembic upgrade head && .venv/bin/python -m scripts.seed
