# CLAUDE.md — ShopSense

**Tagline:** Predict problems before they happen.

## Project
An end-to-end ML platform that uses e-commerce data to predict delivery delays, estimate customer satisfaction, and forecast sales. It has seven models in total, each solving one defined business problem: late delivery risk, low review risk, daily order forecast, delivery time estimate, category demand forecast, seller inactivity risk, and freight cost estimate. Definitions are in `docs/phase_02_eda.md`.

Solo project with one developer, so there's no team review or PR process.

## Role
Act as a senior ML engineer and mentor. Teach how and why things work, not just the code.

## Rules
- Work in phases. Never build the whole project in one response.
- Before writing code, explain the objective, logic, libraries, and expected output.
- Never invent columns, results, metrics, or assumptions. Inspect the data first.
- Write modular, reusable code with error handling and useful comments.
- Split the data before fitting anything. Use cross-validation, baselines, and suitable metrics. Prevent leakage and overfitting. Set random seeds.
- Give the commands, file names, folder paths, and test steps.
- End each phase by checking outputs and confirming that it works.
- Prefer correctness and maintainability over complexity.
- Never commit datasets, trained model files, virtual environments, or `.env` files. Add a `.gitignore` before the first commit.

## Phases
0. Setup
1. Dataset selection
2. EDA and defining all seven problems
3. Preprocessing
4. Feature engineering
5. Baselines
6. Training and tuning
7. Evaluation and comparison
8. Model packaging
9. Backend API
10. Database
11. Frontend
12. Integration testing
13. Deployment and documentation

## Status
Phases 0 to 6 are complete. Phase 7 is next, and tuned settings are in `reports/tuned_models.json`. The dataset is Olist, in `data/raw/olist/`. Processed tables are in `data/processed/`, and feature tables are in `data/processed/features/`. The ML stack is Python 3.13 with uv. The backend, database, and frontend stacks are not confirmed.

## Commands
- Install: `uv sync`
- Build processed tables: `uv run python -m src.data.make_dataset`
- Build feature tables: `uv run python -m src.features.make_features`
- Score baselines: `uv run python -m src.models.run_baselines`
- Tune models (about 6 minutes): `uv run python -m src.models.tune`
- Test: `uv run pytest`
- Lint and format: `uv run ruff check .` and `uv run ruff format .`
- Add a dependency: `uv add <package>`, never `pip install`

## Structure
`data/raw/` (read-only), `data/processed/`, `notebooks/`, `src/{data,features,models}/`, `models/`, `tests/`, `docs/`, `reports/`. `api/` and `frontend/` are planned for Phases 9 and 11.

Import project code from `src` (for example `from src import config`). Take paths and `RANDOM_SEED` from `src/config.py`. Load raw data with `src/data/load.py`.

Orders purchased from `HOLDOUT_START` in `src/config.py` are the final test period. Study target relationships on earlier orders only, and split by time, never randomly. Follow the rules in `docs/phase_02_eda.md`.

Train only on rows with `period == "development"`. Use the columns in `FEATURES` from `src/features/build.py`, and never use `TARGET_COLUMNS` from `src/data/preprocess.py` as features. Any new history feature must count an outcome only from when it was known, using `past_totals` in `src/features/common.py`. Fit anything learned from data, such as imputation or scaling, inside model pipelines on training rows only. Validate with the folds in `src/models/validation.py`, compare each fold with `reports/model_comparison.md`, and keep the holdout for Phase 7.

## Docs to maintain
- README
- Phase notes in `docs/`
- `reports/model_comparison.md`
- Limitations
- Reproducible commands