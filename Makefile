.PHONY: develop test test-cov check format clean repos run help dashboard dashboard-dev

# ─── Setup ───────────────────────────────────────────────
develop:			## Install all dependencies
	uv sync --all-extras

# ─── Testing ─────────────────────────────────────────────
test:				## Run tests (excludes slow/frontend)
	uv run pytest tests/ -v --tb=short -m "not slow"

test-all:			## Run all tests including frontend builds
	uv run pytest tests/ -v --tb=short

test-cov:			## Run tests with coverage report
	uv run pytest tests/ -v --tb=short -m "not slow" --cov=factory --cov-report=term-missing

# ─── Code Quality ────────────────────────────────────────
check:				## Full lint suite (ruff + mypy)
	uv run ruff check factory/ tests/
	uv run ruff format --check factory/ tests/
	uv run mypy factory/

format:				## Auto-format code
	uv run ruff format factory/ tests/
	uv run ruff check --fix factory/ tests/

# ─── Dark Factory CLI ────────────────────────────────────
repos:				## List all GitHub repos
	uv run dark-factory repos

run:				## Run factory on all open issues (usage: make run repo=weather-api)
	uv run dark-factory run --repo $(repo)

start:				## Start a single job (usage: make start repo=weather-api issue=1)
	uv run dark-factory start --repo $(repo) --issue $(issue)

create-issue:			## Create issue (usage: make create-issue repo=weather-api title="Add caching")
	uv run dark-factory create-issue --repo $(repo) --title "$(title)" --editor

retry:				## Retry failed tasks (usage: make retry repo=weather-api issue=1)
	uv run dark-factory retry --repo $(repo) --issue $(issue)

# ─── Dashboard ───────────────────────────────────────────
dashboard:			## Run the dashboard server
	uv run uvicorn factory.dashboard.app:app --port $$(python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('DASHBOARD_PORT', '8420'))")

dashboard-dev:			## Run the dashboard server with reload
	uv run uvicorn factory.dashboard.app:app --reload --port $$(python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('DASHBOARD_PORT', '8420'))")

# ─── Housekeeping ────────────────────────────────────────
clean:				## Remove build artifacts
	rm -rf .venv __pycache__ .pytest_cache .mypy_cache dist *.egg-info

clean-state:			## Clear all saved job state
	rm -rf ~/.dark-factory/state

# ─── Help ────────────────────────────────────────────────
help:				## Show this help
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
