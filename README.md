# ShopSense

Predict problems before they happen.

An end-to-end ML platform that uses e-commerce data to predict delivery delays, estimate customer satisfaction, and forecast sales.

## Setup

Requires [uv](https://docs.astral.sh/uv/). It installs the Python version in `.python-version` and the exact packages in `uv.lock`.

```bash
uv sync
```

## Commands

```bash
uv run pytest                 # run the tests
uv run ruff check .           # lint
uv run ruff format .          # format
uv add <package>              # add a dependency and update the lockfile
```

## Status

See `docs/` for notes on each phase.
