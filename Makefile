.PHONY: develop test check format clean

develop:			## Create virtualenv with dev dependencies
	python -m venv .venv && .venv/bin/pip install -e ".[dev]"

test:				## Run all tests
	pytest tests/ -v --tb=short

check:				## Full lint suite
	ruff check factory/ tests/
	ruff format --check factory/ tests/
	mypy factory/

format:				## Auto-format
	ruff format factory/ tests/
	ruff check --fix factory/ tests/

clean:				## Remove build artifacts
	rm -rf .venv __pycache__ .pytest_cache .mypy_cache dist *.egg-info
