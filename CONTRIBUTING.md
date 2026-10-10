# Contributing to Harness

Thank you for your interest in contributing to Harness.

## Development Setup

```bash
# Clone and install
git clone https://github.com/Quattro-Commas/harness.git
cd harness
uv sync

# Run tests
uv run pytest -v

# Lint and type-check
uv run ruff check .
uv run mypy .
```

## Pull Request Process

1. Fork the repository and create a branch from `main`.
2. Add or update tests for any changed functionality.
3. Ensure `uv run pytest`, `uv run ruff check .`, and `uv run mypy .` all pass.
4. Update documentation if your change affects user-facing behavior.
5. Submit a pull request with a clear description of the change.

## Code Style

- Python 3.10+ with type hints.
- Ruff for linting and formatting (line length 110).
- mypy for type checking.
- Follow existing patterns in the codebase.

## Reporting Issues

Please use the [issue tracker](https://github.com/Quattro-Commas/harness/issues) for bug reports and feature requests. For security vulnerabilities, see [SECURITY.md](SECURITY.md).

## License

By contributing, you agree that your contributions will be licensed under the AGPL-3.0.