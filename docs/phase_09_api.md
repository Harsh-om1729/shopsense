
# Phase 9: Backend API

The API uses FastAPI, and the code is in `api/`.

## Run it

```bash
uv run uvicorn api.main:app --reload
```

Interactive docs are at http://127.0.0.1:8000/docs. Run `uv run python -m src.models.package` first if `models/` is empty.

## Endpoints

| Method | Path | Purpose | Source |
|---|---|---|---|
| GET | `/health` | What's loaded | System |
| GET | `/models` | Every package, its status, and its verdict | System |
| POST | `/predict/freight` | Freight for one product on a route | Trained model |
| POST | `/predict/delivery-time` | Estimated delivery days by state | Simple rule |
| POST | `/predict/late-delivery` | Always returns 503 with the reason | Held |
| GET | `/forecast/orders` | Daily orders for up to 28 days | Simple rule |
| GET | `/forecast/category` | Weekly items for a top-10 category | Simple rule |
| GET | `/reviews/queue` | Recent orders ranked by low-review risk | Trained model |
| GET | `/sellers/at-risk` | Sellers likely to stop selling | Trained model |

## Errors

| Status | Meaning |
|---|---|
| 422 | The request is invalid, such as an unknown state or an out-of-range date |
| 503 | The model is held, missing, or built with a different scikit-learn version |

Requests with unknown fields are rejected, so a misspelled field can't be silently ignored.

## Decisions

- **FastAPI** reuses the Python code directly, and validates and documents requests automatically.
- **Freight features come from training code.** The API calls `build_freight_features`, so serving can't drift from training.
- **Stored data sits behind `Services`.** Phase 10 moved it from Parquet to the database without changing any paths.
- **The API keeps the Phase 7 verdicts.** The review queue has no alert, late delivery never predicts, and seller results show revenue and days since last sale.
- **Queue responses include `scored_on_training_data: true`,** so nobody mistakes those scores for a fresh test.

## Checks

- **Tests:** all 151 pass.
- **Skew:** a stored row's raw fields sent through the API match the prediction from its training features.
- **Live server:** all 9 endpoints were called over HTTP and gave the expected statuses, including 422 for invalid requests and 503 for the held model.
- **Bug found by tests:** freight requests without coordinates crashed. They now work, and the model handles the missing values.

## Known gaps

- **Queue scores are optimistic.** The final models trained on those rows, so don't read them as evidence of performance.
- **The review queue window is short and historic.** It covers the last 7 days of stored data, which ends in August 2018.
- **There's no authentication.** Run it locally only until that's added.
- **There's no CORS yet.** The frontend will need it in Phase 11.
- **A test warning remains.** `TestClient` warns that Starlette is moving away from `httpx`. It doesn't affect behaviour.

## Verify

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```
