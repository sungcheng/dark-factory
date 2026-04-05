.PHONY: develop test fast-test check format clean docker-build docker-run

develop:			## Install all dependencies
	uv sync --all-extras

test:				## Run all tests
	uv run pytest tests/ -v --tb=short

fast-test:			## Run tests excluding slow markers
	uv run pytest tests/ -v --tb=short -m "not slow"

check:				## Full lint suite
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/
	uv run mypy src/

format:				## Auto-format
	uv run ruff format src/ tests/
	uv run ruff check --fix src/ tests/

clean:				## Remove build artifacts
	rm -rf .venv __pycache__ .pytest_cache .mypy_cache dist *.egg-info

docker-build:			## Build Docker image
	docker build -t {{SERVICE_NAME}}:latest .

docker-run:			## Run Docker container
	docker run -p 8000:8000 {{SERVICE_NAME}}:latest
