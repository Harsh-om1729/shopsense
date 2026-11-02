"""Package the models and rules chosen in Phase 7.

Run after evaluate with: uv run python -m src.models.package

Trained models are refitted on all known data with frozen settings, so their
holdout scores describe the earlier fit. Metadata records this.
"""

import json
import platform
import subprocess
from datetime import UTC, datetime

import joblib
import numpy as np
import pandas as pd
import sklearn

from src import config
from src.features.build import FEATURES, daily_lag_input, weekly_lag_input
from src.models.pipelines import make_boosted_classifier, make_boosted_regressor
from src.models.predictor import METADATA_FILE, MODEL_FILE, RULE_FILE, load_predictor

VERSION = "1.0.0"
CHECK_ROWS = 200

TRAINED_MODELS = [
    {
        "name": "low_review_risk",
        "problem": "2. Low review risk",
        "table": "reviews",
        "target": "is_low",
        "kind": "ranking",
        "note": "Use the ranking, such as a top-N queue. The fixed alert missed its target.",
    },
    {
        "name": "seller_inactivity_risk",
        "problem": "6. Seller inactivity risk",
        "table": "seller_snapshots",
        "target": "is_inactive",
        "kind": "alert",
        "note": "Days since last sale caught more at-risk revenue on the holdout.",
    },
    {
        "name": "freight_cost",
        "problem": "7. Freight cost estimate",
        "table": "freight",
        "target": "freight_value",
        "kind": "regression",
        "output": "predicted_freight",
        "note": "Freight rose during the holdout, and the cause is unclear.",
    },
]

HELD_MODEL = {
    "name": "late_delivery_risk",
    "problem": "1. Late delivery risk",
    "status": "held",
    "reason": (
        "On the holdout it was 1.15 times a constant score, and its ranking didn't work. "
        "Retrain and test it on newer data first."
    ),
}


def source_version() -> dict:
    """Return the current commit, and whether uncommitted changes exist."""

    def git(*arguments):
        result = subprocess.run(
            ["git", *arguments], cwd=config.PROJECT_ROOT, capture_output=True, text=True
        )
        return result.stdout.strip() if result.returncode == 0 else None

    return {
        "commit": git("rev-parse", "--short", "HEAD"),
        "dirty": bool(git("status", "--porcelain")),
    }


def environment() -> dict:
    """Return the versions a package was built with."""
    return {
        "python": platform.python_version(),
        "scikit-learn": sklearn.__version__,
        "pandas": pd.__version__,
        "numpy": np.__version__,
    }


def holdout_evidence(problem: str) -> dict:
    """Return the Phase 7 scores for a problem."""
    comparisons = pd.read_csv(config.REPORTS_DIR / "holdout_comparison.csv")
    row = comparisons[comparisons["problem"] == problem].iloc[0]
    evidence = {
        "metric": row["metric"],
        "simple_rule": row["simple_rule"],
        "rule_score": round(float(row["rule_score"]), 4),
        "tuned_score": round(float(row["tuned_score"]), 4),
        "interval": [round(float(row["interval_low"]), 4), round(float(row["interval_high"]), 4)],
        "verdict": row["verdict"],
    }
    alerts = pd.read_csv(config.REPORTS_DIR / "holdout_alerts.csv")
    alert = alerts[alerts["problem"] == problem]
    if not alert.empty:
        evidence["alert_precision"] = round(float(alert["precision"].iloc[0]), 4)
        evidence["alert_recall"] = round(float(alert["recall"].iloc[0]), 4)
    return evidence


def base_metadata(entry: dict, table: pd.DataFrame, time_column: str) -> dict:
    """Return metadata shared by every package."""
    return {
        "name": entry["name"],
        "version": VERSION,
        "status": entry.get("status", "active"),
        "problem": entry["problem"],
        "kind": entry["kind"],
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": source_version(),
        "environment": environment(),
        "training_data": {
            "rows": len(table),
            "first": str(table[time_column].min().date()),
            "last": str(table[time_column].max().date()),
        },
    }


def fit_trained(entry: dict, settings: dict, table: pd.DataFrame):
    """Fit a model with its frozen family and settings."""
    spec = FEATURES[entry["table"]]
    params = settings["params"]
    if settings["family"] == "boosted_classifier":
        model = make_boosted_classifier(spec, params)
    elif settings["family"] == "boosted_median":
        model = make_boosted_regressor(spec, params, loss="absolute_error")
    else:
        raise ValueError(f"Can't package family {settings['family']}.")
    return model.fit(table, table[entry["target"]])


def daily_rule_artifact(table: pd.DataFrame) -> dict:
    """Return the order history the daily rule needs."""
    ordered = table.sort_values("date")
    orders = daily_lag_input(ordered)
    dates = ordered["date"].dt.strftime("%Y-%m-%d").tolist()
    return {"dates": dates, "orders": [None if pd.isna(v) else float(v) for v in orders]}


def weekly_rule_artifact(table: pd.DataFrame) -> dict:
    """Return the item history the weekly rule needs, by category."""
    ordered = table.sort_values(["category", "week_end"]).reset_index(drop=True)
    items = weekly_lag_input(ordered)
    grid = ordered.assign(lag_input=items).pivot(
        index="week_end", columns="category", values="lag_input"
    )
    return {
        "week_ends": grid.index.strftime("%Y-%m-%d").tolist(),
        "items": {
            category: [None if pd.isna(v) else float(v) for v in grid[category]]
            for category in grid.columns
        },
    }


def delivery_rule_artifact(table: pd.DataFrame) -> dict:
    """Return the median delivery days by customer state."""
    medians = table.groupby("customer_state")["days_to_deliver"].median()
    return {
        "group_column": "customer_state",
        "medians": {state: round(float(value), 4) for state, value in medians.items()},
        "fallback": round(float(table["days_to_deliver"].median()), 4),
    }


def write_package(name: str, metadata: dict, rule: dict | None = None, model=None) -> None:
    """Write a package's files."""
    directory = config.MODELS_DIR / name
    directory.mkdir(parents=True, exist_ok=True)
    if rule is not None:
        (directory / RULE_FILE).write_text(json.dumps(rule, indent=2) + "\n")
    if model is not None:
        joblib.dump(model, directory / MODEL_FILE)
    (directory / METADATA_FILE).write_text(json.dumps(metadata, indent=2) + "\n")


def package_trained(entry: dict, settings: dict) -> dict:
    """Refit a model on all known rows, save it, and check that it reloads identically."""
    table = pd.read_parquet(config.FEATURES_DIR / f"{entry['table']}.parquet")
    model = fit_trained(entry, settings, table)
    time_column = "snapshot_date" if entry["table"] == "seller_snapshots" else None
    metadata = base_metadata(entry, table, time_column or "order_purchase_timestamp")
    metadata.update(
        {
            "features": FEATURES[entry["table"]],
            "family": settings["family"],
            "params": settings["params"],
            "holdout": holdout_evidence(entry["problem"]),
            "holdout_note": "Scores come from an earlier fit with the same settings.",
            "note": entry["note"],
        }
    )
    if entry["kind"] == "alert":
        metadata["alert_cutoff"] = settings["alert_cutoff"]
        metadata["target_precision"] = settings["target_precision"]
    if "output" in entry:
        metadata["output"] = entry["output"]
    write_package(entry["name"], metadata, model=model)

    sample = table.tail(CHECK_ROWS)
    reloaded = load_predictor(entry["name"]).predict(sample)
    numeric = sample[metadata["features"]["numeric"]].astype(float)
    frame = pd.concat([numeric, sample[metadata["features"]["categorical"]]], axis=1)
    if entry["kind"] == "regression":
        expected = np.clip(model.predict(frame), 0, None)
        actual = reloaded[entry["output"]]
    else:
        expected = model.predict_proba(frame)[:, 1]
        actual = reloaded["risk_score"]
    if not np.allclose(expected, actual):
        raise ValueError(f"{entry['name']} changed when reloaded.")
    return metadata


def package_rules() -> list[dict]:
    """Package the three problems where a simple rule won."""
    daily = pd.read_parquet(config.FEATURES_DIR / "daily_orders.parquet")
    weekly = pd.read_parquet(config.FEATURES_DIR / "weekly_category.parquet")
    delivery = pd.read_parquet(config.FEATURES_DIR / "delivery.parquet")

    rules = [
        (
            {
                "name": "daily_orders_rule",
                "problem": "3. Daily order forecast",
                "kind": "daily_rule",
                "output": "predicted_orders",
                "note": "The tuned model had lower error, but 12 weeks couldn't rule out luck.",
            },
            daily_rule_artifact(daily),
            daily,
            "date",
        ),
        (
            {
                "name": "delivery_time_rule",
                "problem": "4. Delivery time estimate",
                "kind": "group_median",
                "output": "predicted_days",
                "note": "For estimates only. Keep Olist's promises for customers.",
            },
            delivery_rule_artifact(delivery),
            delivery,
            "order_purchase_timestamp",
        ),
        (
            {
                "name": "category_demand_rule",
                "problem": "5. Category demand forecast",
                "kind": "weekly_rule",
                "output": "predicted_items",
                "note": "Covers the top 10 categories only.",
            },
            weekly_rule_artifact(weekly),
            weekly,
            "week_end",
        ),
    ]

    packaged = []
    for entry, rule, table, time_column in rules:
        metadata = base_metadata(entry, table, time_column)
        metadata.update(
            {
                "output": entry["output"],
                "holdout": holdout_evidence(entry["problem"]),
                "note": entry["note"],
            }
        )
        write_package(entry["name"], metadata, rule=rule)
        load_predictor(entry["name"])
        packaged.append(metadata)
    return packaged


def package_held() -> dict:
    """Record the held model, so asking for it gives a clear reason."""
    metadata = {
        **HELD_MODEL,
        "version": VERSION,
        "holdout": holdout_evidence(HELD_MODEL["problem"]),
    }
    write_package(HELD_MODEL["name"], metadata)
    return metadata


def write_registry(packages: list[dict]) -> None:
    """Write a tracked summary, since packaged files stay out of git."""
    registry = [
        {
            key: package.get(key)
            for key in ["name", "problem", "status", "kind", "version", "training_data", "source"]
        }
        | {
            "verdict": package["holdout"]["verdict"],
            "note": package.get("note") or package.get("reason"),
        }
        for package in packages
    ]
    path = config.REPORTS_DIR / "model_registry.json"
    path.write_text(json.dumps(registry, indent=2) + "\n")


def main() -> None:
    chosen = json.loads((config.REPORTS_DIR / "tuned_models.json").read_text())
    packages = [package_trained(entry, chosen[entry["problem"]]) for entry in TRAINED_MODELS]
    packages += package_rules()
    packages.append(package_held())
    write_registry(packages)
    for package in packages:
        print(f"{package['name']}: {package['status']}")


if __name__ == "__main__":
    main()
