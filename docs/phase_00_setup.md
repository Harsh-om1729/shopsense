# Phase 0: Setup

## Decisions

- **Python 3.13, managed with uv.** `.python-version` and `uv.lock` make the environment reproducible.
- **`src` is imported as a package**, for example `from src import config`. It isn't installed, so `pytest` finds it through `pythonpath` in `pyproject.toml`.
- **Paths and the random seed live in `src/config.py`.** Use `RANDOM_SEED` in every split, cross-validation run, and model.
- **`api/` and `frontend/` are not created yet.** Their stack is decided in Phases 9 and 11.
- **Data and trained models stay out of git.** `.gitignore` keeps these folders but ignores their contents.

## Verify

```bash
uv sync --locked
uv run pytest
uv run ruff check .
uv run ruff format --check .
```
