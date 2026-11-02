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
uv run python -m src.data.make_dataset  # build the tables in data/processed/
uv run python -m src.features.make_features  # build the feature tables
uv run pytest                 # run the tests
uv run ruff check .           # lint
uv run ruff format .          # format
uv add <package>              # add a dependency and update the lockfile
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/01_eda.ipynb  # rerun EDA
```

## Data

Download the Olist dataset and put its 9 CSV files in `data/raw/olist/`. Data files aren't committed to git.

## Status

See `docs/` for notes on each phase.
