# Contributing

## Development setup

This project uses **pixi** for environment management.

```bash
# Install pixi (if not already installed)
curl -fsSL https://pixi.sh/install.sh | bash

# Clone and enter the project
git clone https://github.com/kubrian/vibview.git
cd vibview

# Install all dependencies
pixi install

# Activate the environment
pixi shell
```

## Pre-commit hooks

Install pre-commit hooks before making changes:

```bash
pixi run pre-commit install
```

Hooks are defined in `.pre-commit-config.yaml` and are automatically run on every commit. You can also run them manually on all files:

```bash
pixi run pre-commit run --all-files
```

## Quality gate

Before submitting, run the full quality gate:

```bash
pre-commit run --all-files && pixi run pytest
```

This runs:

- **Linting:** ruff (format + check), prettier (markdown/yaml)
- **Validation:** trailing-whitespace, end-of-file-fixer, check-yaml
- **Tests:** pytest with coverage (fail-under 80%)

## Code conventions

- Google-style docstrings for all public functions, methods, and classes.
- Docstrings are the source of truth for `docs/api.md` (auto-generated via mkdocstrings).
- Write the failing test first, then implement.
- No dead code, no silent failures, no bare `except`.
- Conventional commits: `type: description` (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`).
- Prefer the simplest correct solution (YAGNI).

## Pull request process

1. Create a feature branch from `main`.
2. Implement your changes.
3. Run the quality gate.
4. Submit a PR against `main`.
5. Ensure CI passes.
