.PHONY: develop test test-cov check format clean repos run help

# ─── Setup ───────────────────────────────────────────────
develop:			## Install all dependencies
	uv sync --all-extras

# ─── Testing ─────────────────────────────────────────────
test:				## Run all tests
	uv run pytest tests/ -v --tb=short

test-cov:			## Run tests with coverage report
	uv run pytest tests/ -v --tb=short --cov=factory --cov-report=term-missing

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

run:				## Run factory on all open issues (usage: make run REPO=weather-api)
	uv run dark-factory run --repo $(REPO)

start:				## Start a single job (usage: make start REPO=weather-api ISSUE=1)
	uv run dark-factory start --repo $(REPO) --issue $(ISSUE)

retry:				## Retry failed tasks (usage: make retry REPO=weather-api ISSUE=1)
	uv run dark-factory retry --repo $(REPO) --issue $(ISSUE)

# ─── Housekeeping ────────────────────────────────────────
clean:				## Remove build artifacts
	rm -rf .venv __pycache__ .pytest_cache .mypy_cache dist *.egg-info

clean-state:			## Clear all saved job state
	rm -rf ~/.dark-factory/state

# ─── Help ────────────────────────────────────────────────
help:				## Show this help
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
