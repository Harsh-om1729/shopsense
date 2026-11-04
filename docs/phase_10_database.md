# Phase 10: Database

The database is SQLite, used through SQLAlchemy. The code is in `src/db/`, and the file is `data/processed/shopsense.db`, which isn't committed. The API no longer reads Parquet files.

## Build it

```bash
uv run python -m src.db.load
```

Run it after `src.features.make_features`. It takes a few seconds, and it can be repeated safely.

## Tables

| Table | Rows | Contents |
|---|---:|---|
| `orders` | 98,390 | Order status, dates, and customer state |
| `zip_coordinates` | 19,010 | Median coordinates for each zip prefix |
| `review_features` | 94,600 | IDs and allowed features for the review queue |
| `seller_snapshots` | 16,390 | IDs and allowed features for seller risk |
| `predictions` | Grows | One row per served request |

## Decisions

- **Targets aren't stored.** `review_features` and `seller_snapshots` have no `is_low`, `review_score`, or `is_inactive`. Serving code can't leak an answer the database doesn't hold, and a test checks this.
- **Loads are all-or-nothing.** Each load is one transaction, so a failure leaves the old data intact.
- **Reloading keeps the log.** Only the four data tables are replaced.
- **Logging can't break predictions.** A failed log write records a warning, and the caller still gets an answer.
- **Foreign keys are on,** because SQLite ignores them by default. WAL mode stops log writes from blocking reads.
- **Freight accepts zip prefixes.** `customer_zip_prefix` and `seller_zip_prefix` replace coordinates. Sending both is rejected, and `distance_known: false` marks an estimate without a distance.
- **Queues log a summary,** such as how many rows were returned, not every row.

## API changes

Paths are unchanged. `/predict/freight` accepts the two zip fields and returns `distance_known`, and `/health` returns `database_ready`. Without a loaded database, `/health` reports `degraded`, and the queues return 503 with instructions.

## Checks

- **Tests:** all 175 pass.
- **Same answers as before:** review and seller scores from the database exactly match scores from the feature files.
- **Safety:** tests cover failed loads, foreign keys, repeat loads, and logging failures.
- **Live server:** all endpoints responded as expected, and 7 requests produced 7 log rows with model versions.
- **Integrity:** SQLite's integrity and foreign key checks passed.

The test log rows were removed, so the log starts empty.

## Known gaps

- **Missing product details weaken freight estimates.** With no dimensions, the same route gave 27.31 against 15.26 with them. Training data almost never lacked dimensions, so the model has little to go on. `distance_known` only covers distance.
- **The log doesn't record outcomes yet.** It shows what was predicted, but comparing that with what happened needs new data.
- **The log grows without limit.** There's no cleanup yet.
- **SQLite suits one server.** A busier deployment would need PostgreSQL.
- **There's no migration tool.** A schema change means deleting the file and reloading, which would lose the log.
- **Queue scores are still optimistic,** for the reason in `docs/phase_09_api.md`.

## Verify

```bash
uv run python -m src.db.load
uv run pytest
uv run ruff check .
uv run ruff format --check .
```
