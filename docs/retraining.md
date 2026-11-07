# Retraining on new data

The holdout showed that conditions change fast, so models need retraining. The original holdout has also been used up, which means any new claim about performance needs **new orders that no model has seen**.

## 1. Add the data

1. Put the new Olist export in `data/raw/olist/`, with the same 9 files and columns.
2. Check it loads with `uv run python -c "from src.data.load import load_all; print({k: len(v) for k, v in load_all().items()})"`.
3. Inspect it before changing anything, as in Phase 2. Look at the date range, the last complete day, missing values, and any new categories.

## 2. Move the dates

In `src/config.py`:

| Setting | Change it to |
|---|---|
| `LAST_ORDER_DATE` | The last complete day in the new data |
| `HOLDOUT_START` | A date after which no model has been trained or tuned. The most recent 2 to 3 months is typical |
| `EMBARGO_DAYS` | Keep it at 30 unless deliveries now take much longer |

Never move `HOLDOUT_START` back into data a model has already seen.

## 3. Rebuild and re-validate

```bash
uv run python -m src.data.make_dataset
uv run python -m src.features.make_features      # check that it reports 0 leak alarms
uv run pytest tests/test_feature_leakage.py      # development rows must ignore the holdout
uv run python -m src.models.run_baselines
uv run python -m src.models.tune                 # about 6 minutes
```

Compare each fold with `reports/model_comparison.md`, not only the averages. Late delivery needs particular attention, since it failed last time.

## 4. Test once on the new holdout

1. Before running anything, update the locked plan in `docs/phase_07_evaluation.md`: the verdict rules, the simple rules, and what counts as success. Add the rule that a model must also beat a constant score, since that loophole let late delivery through last time.
2. Remove the old results, so the one-time guard allows a new run: `rm reports/holdout_*.csv`.
3. Run `uv run python -m src.models.evaluate`.
4. Apply the verdicts as written, and don't tune after seeing the results.

## 5. Package and release

```bash
uv run python -m src.models.package   # retrains on all data with the chosen settings
uv run python -m src.db.load
scripts/check_all.sh --rebuild
```

- Raise `VERSION` in `src/models/package.py`, so logged predictions show which version made them.
- Update `docs/model_cards.md` with the new scores.
- If a model's verdict changes, update `TRAINED_MODELS` or the rules in `src/models/package.py`, then the Overview page notes.
- Restart the app with `docker compose up --build`.

## 6. Monitor

The `predictions` table records every served prediction, with its model and version. Once outcomes arrive, compare them with what was predicted, for example the actual freight against `predicted_freight`. Retrain when the error clearly drifts from the holdout scores in the model cards.
