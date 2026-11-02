"""Build and save the feature tables, and report each feature's signal.

Run after make_dataset with: uv run python -m src.features.make_features
"""

import pandas as pd

from src import config
from src.data.load import load_table
from src.data.make_dataset import TABLE_KEYS
from src.data.preprocess import TARGET_COLUMNS
from src.features.build import FEATURES, build_all_features

# Each model's target and the table it uses.
TARGETS = {
    "delivery": ["is_late", "days_to_deliver"],
    "reviews": ["is_low"],
    "daily_orders": ["orders"],
    "weekly_category": ["items"],
    "seller_snapshots": ["is_inactive"],
    "freight": ["freight_value"],
}

# A single feature this close to a target is usually a leak, not a discovery.
LEAK_ALARM = 0.9


def load_processed() -> dict[str, pd.DataFrame]:
    """Read the processed tables, with a clear error if they haven't been built."""
    processed = {}
    for name in TABLE_KEYS:
        path = config.DATA_PROCESSED_DIR / f"{name}.parquet"
        if not path.is_file():
            raise FileNotFoundError(f"Missing {path}. Run src.data.make_dataset first.")
        processed[name] = pd.read_parquet(path)
    return processed


def validate(features: dict[str, pd.DataFrame]) -> None:
    """Raise ValueError if a table is malformed or a target is used as a feature."""
    for name, table in features.items():
        spec = FEATURES[name]
        columns = spec["numeric"] + spec["categorical"]

        missing = set(columns) - set(table.columns)
        if missing:
            raise ValueError(f"{name} is missing features: {missing}.")

        forbidden = set(TARGET_COLUMNS.get(name, [])) | set(TARGETS[name])
        leaked = set(columns) & forbidden
        if leaked:
            raise ValueError(f"{name} uses targets as features: {leaked}.")

        if table.duplicated(TABLE_KEYS[name]).any():
            raise ValueError(f"{name} has duplicate rows.")


def signal_report(features: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Return each numeric feature's rank correlation with its target on development rows."""
    rows = []
    for name, table in features.items():
        development = table[table["period"] == "development"]
        for target in TARGETS[name]:
            for feature in FEATURES[name]["numeric"]:
                rows.append(
                    {
                        "table": name,
                        "target": target,
                        "feature": feature,
                        "missing_share": round(development[feature].isna().mean(), 4),
                        "spearman": round(
                            development[feature].corr(development[target], method="spearman"), 4
                        ),
                    }
                )
    return pd.DataFrame(rows)


def main() -> None:
    raw = {name: load_table(name) for name in ["order_items", "orders"]}
    features = build_all_features(load_processed(), raw)
    validate(features)

    config.FEATURES_DIR.mkdir(parents=True, exist_ok=True)
    for name, table in features.items():
        table.to_parquet(config.FEATURES_DIR / f"{name}.parquet", index=False)
        count = len(FEATURES[name]["numeric"]) + len(FEATURES[name]["categorical"])
        print(f"{name}: {len(table):,} rows, {count} features")

    report = signal_report(features)
    report.to_csv(config.REPORTS_DIR / "feature_signal.csv", index=False)

    alarms = report[report["spearman"].abs() >= LEAK_ALARM]
    print(f"Leak alarms: {len(alarms)}")
    if not alarms.empty:
        print(alarms.to_string(index=False))
    print(f"Saved features to {config.FEATURES_DIR}")


if __name__ == "__main__":
    main()
