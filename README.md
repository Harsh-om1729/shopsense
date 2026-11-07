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
uv run python -m src.models.run_baselines  # score baselines in reports/model_comparison.md
uv run python -m src.models.tune  # tune models, about 6 minutes
uv run python -m src.models.evaluate  # one-time holdout test, already run
uv run python -m src.models.package  # build the packages in models/
uv run python -m src.db.load  # load the database
uv run uvicorn api.main:app --reload  # run the API, with docs at http://127.0.0.1:8000/docs
uv run pytest                 # run the tests
uv run ruff check .           # lint
uv run ruff format .          # format
uv add <package>              # add a dependency and update the lockfile
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/01_eda.ipynb  # rerun EDA
```

## Frontend

Run the API first, then in a second terminal:

```bash
cd frontend
npm install
npm run dev      # site at http://localhost:5173
npm test
npm run build
```

If port 8000 is taken, run the API on another port and point the site at it:

```bash
uv run uvicorn api.main:app --port 8010
SHOPSENSE_API_URL=http://127.0.0.1:8010 npm run dev
```

After changing the API, regenerate the frontend's types:

```bash
uv run python -m api.export_openapi
cd frontend && npm run generate:api
```

## Data

Download the Olist dataset and put its 9 CSV files in `data/raw/olist/`. Data files aren't committed to git.

## Status

See `docs/` for notes on each phase. Final model scores and verdicts are in `reports/model_comparison.md`.
