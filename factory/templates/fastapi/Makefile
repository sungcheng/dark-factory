.PHONY: develop test fast-test check format clean docker-build docker-run staging staging-down prod prod-down help

# ─── Setup ───────────────────────────────────────────────
develop:			## Install all dependencies
	uv sync --all-extras

# ─── Testing ─────────────────────────────────────────────
test:				## Run all tests
	uv run pytest tests/ -v --tb=short

fast-test:			## Run tests excluding slow markers
	uv run pytest tests/ -v --tb=short -m "not slow"

# ─── Code Quality ────────────────────────────────────────
check:				## Full lint suite
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/
	uv run mypy src/

format:				## Auto-format
	uv run ruff format src/ tests/
	uv run ruff check --fix src/ tests/

# ─── Docker ──────────────────────────────────────────────
docker-build:			## Build Docker image
	docker build -t {{PROJECT_NAME}}:latest .

docker-run:			## Run Docker container
	docker run -p 8000:8000 {{PROJECT_NAME}}:latest

# ─── Environments ────────────────────────────────────────
staging:			## Start staging (http://localhost:8001)
	docker compose up --build -d
	@echo "Staging running at http://localhost:8001"

staging-down:			## Stop staging
	docker compose down

prod:				## Start production (http://localhost:8000)
	docker compose --profile prod up --build -d
	@echo "Production running at http://localhost:8000"

prod-down:			## Stop production
	docker compose --profile prod down

# ─── Housekeeping ────────────────────────────────────────
clean:				## Remove build artifacts
	rm -rf .venv __pycache__ .pytest_cache .mypy_cache dist *.egg-info

help:				## Show this help
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
