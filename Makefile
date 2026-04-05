.PHONY: develop test check format clean

develop:			## Install all dependencies
	uv sync --all-extras

test:				## Run all tests
	uv run pytest tests/ -v --tb=short

check:				## Full lint suite
	uv run ruff check factory/ tests/
	uv run ruff format --check factory/ tests/
	uv run mypy factory/

format:				## Auto-format
	uv run ruff format factory/ tests/
	uv run ruff check --fix factory/ tests/

clean:				## Remove build artifacts
	rm -rf .venv __pycache__ .pytest_cache .mypy_cache dist *.egg-info
