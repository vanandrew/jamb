# Contributing to jamb

Thanks for your interest in contributing to jamb! This guide will help you get started.

## Getting Started

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) for dependency management

### Setup

1. Fork and clone the repository:

   ```bash
   git clone https://github.com/<your-username>/jamb.git
   cd jamb
   ```

2. Install dependencies:

   ```bash
   uv sync --group dev
   ```

   For documentation work, also install the docs group:

   ```bash
   uv sync --group docs
   ```

3. Install pre-commit hooks:

   ```bash
   uv run pre-commit install
   ```

## Development Workflow

### Running Tests

```bash
uv run pytest
```

Tests run with coverage enabled by default. To run a specific test file or test:

```bash
uv run pytest tests/unit/test_core_models.py
uv run pytest tests/unit/test_core_models.py::test_something -k "keyword"
```

### Linting and Formatting

The project uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```

To auto-fix lint issues:

```bash
uv run ruff check --fix src/ tests/
```

### Type Checking

The project uses [MyPy](https://mypy-lang.org/) with strict mode enabled:

```bash
uv run mypy src/jamb
```

### Pre-commit Hooks

Pre-commit hooks run Ruff and MyPy automatically on each commit. If you installed them during setup, they will catch issues before they reach CI.

## Submitting Changes

1. Create a branch from `main`:

   ```bash
   git checkout -b your-branch-name
   ```

2. Make your changes and ensure all checks pass:

   ```bash
   uv run ruff check src/ tests/
   uv run ruff format --check src/ tests/
   uv run mypy src/jamb
   uv run pytest
   ```

3. Commit your changes with a clear message describing the change.

4. Push your branch and open a pull request against `main`.

### Pull Request Guidelines

- Keep PRs focused on a single change.
- Add tests for new functionality.
- Ensure all CI checks pass (lint, typecheck, tests across Python 3.10--3.13).
- Update documentation if your change affects user-facing behavior.

## Building Documentation

The documentation is built with Sphinx:

```bash
uv sync --group docs
uv run sphinx-build docs docs/_build/html
```

For live-reloading during development:

```bash
uv run sphinx-autobuild docs docs/_build/html
```

## Project Structure

```
src/jamb/
├── cli/              # Click CLI commands
├── config/           # Configuration loading
├── core/             # Domain models and errors
├── matrix/           # Traceability matrix generation
├── publish/          # Document publishing (HTML, DOCX)
├── pytest_plugin/    # pytest integration (markers, hooks)
├── storage/          # Document discovery, validation, graph building
└── yaml_io.py        # YAML import/export
```

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
