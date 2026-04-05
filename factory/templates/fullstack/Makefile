.PHONY: develop test check format staging staging-down prod prod-down help

# ─── Setup ───────────────────────────────────────────────
develop:			## Install all dependencies
	cd backend && uv sync --all-extras
	cd frontend && npm install

# ─── Testing ─────────────────────────────────────────────
test:				## Run backend tests
	cd backend && uv run pytest tests/ -v --tb=short

# ─── Code Quality ────────────────────────────────────────
check:				## Full backend lint suite
	cd backend && uv run ruff check src/ tests/
	cd backend && uv run ruff format --check src/ tests/
	cd backend && uv run mypy src/

format:				## Auto-format backend
	cd backend && uv run ruff format src/ tests/
	cd backend && uv run ruff check --fix src/ tests/

# ─── Environments ────────────────────────────────────────
staging:			## Start staging (backend :8001, frontend :3001)
	docker compose up --build -d
	@echo "Backend  running at http://localhost:8001"
	@echo "Frontend running at http://localhost:3001"

staging-down:			## Stop staging
	docker compose down

prod:				## Start production (backend :8000, frontend :3000)
	docker compose --profile prod up --build -d
	@echo "Backend  running at http://localhost:8000"
	@echo "Frontend running at http://localhost:3000"

prod-down:			## Stop production
	docker compose --profile prod down

# ─── Housekeeping ────────────────────────────────────────
clean:				## Remove build artifacts
	rm -rf backend/.venv backend/__pycache__ backend/.pytest_cache backend/.mypy_cache backend/dist
	rm -rf frontend/node_modules frontend/dist

help:				## Show this help
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
