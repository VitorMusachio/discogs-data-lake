# Common tasks. Run `make help` for the list.
PYTHON ?= .venv/bin/python
export PYTHONPATH := src

.PHONY: help install lint format test lineage lineage-check validate check up down test-integration logs

help:  ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-18s %s\n", $$1, $$2}'

install:  ## Create .venv with dev dependencies and install the git hooks
	python3 -m venv .venv
	.venv/bin/pip install -q -r requirements-dev.txt
	.venv/bin/pre-commit install

lint:  ## ruff (Python) + sqlfluff (Spark SQL)
	$(PYTHON) -m ruff check src tests dags
	$(PYTHON) -m ruff format --check src tests dags
	$(PYTHON) -m sqlfluff lint sql

format:  ## Auto-fix Python and SQL style
	$(PYTHON) -m ruff check --fix src tests dags
	$(PYTHON) -m ruff format src tests dags
	$(PYTHON) -m sqlfluff fix sql --force

test:  ## Unit tests (local Spark, needs Java 17+)
	$(PYTHON) -m pytest tests/unit

lineage:  ## Regenerate docs/lineage.{md,json} from pipelines/ and sql/
	$(PYTHON) -m discogs_pipeline.lineage generate

lineage-check:  ## Fail if the lineage is inconsistent or docs/lineage.* are stale
	$(PYTHON) -m discogs_pipeline.lineage check

validate: lineage-check  ## Validate pipeline specs and lineage (alias)

check: lint lineage-check test  ## Everything CI runs

up:  ## Build and start the local stack
	docker compose up -d --build

down:  ## Stop the local stack
	docker compose down

test-integration:  ## Integration tests inside the Airflow container (stack must be up)
	docker compose exec -T airflow-scheduler python -m pytest tests/integration

logs:  ## Follow scheduler logs
	docker compose logs -f airflow-scheduler
