.PHONY: install test lint typecheck run clean

install:
	uv sync

test:
	uv run pytest -v

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run mypy .

run:
	uv run harness --help

clean:
	rm -rf __pycache__ .mypy_cache .ruff_cache .pytest_cache dist build *.egg-info