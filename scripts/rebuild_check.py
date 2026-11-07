"""Rebuild everything from the raw CSVs and confirm the API's answers don't change.

Run with: uv run python -m scripts.rebuild_check

It records key answers, reruns every build step (dataset, features, packages,
database), records them again, and fails if anything differs. Tuning isn't
rerun, because its settings are frozen in reports/tuned_models.json.

Packaging rewrites reports/model_registry.json with the current commit. The
check restores it afterwards, so running it doesn't leave a changed file in git.
"""

import math
import subprocess
import sys
import time

from api.services import Services
from src import config
from src.db.store import Store

BUILD_STEPS = [
    "src.data.make_dataset",
    "src.features.make_features",
    "src.models.package",
    "src.db.load",
]

FREIGHT_REQUEST = {
    "customer_state": "SP",
    "seller_state": "RJ",
    "customer_zip_prefix": 1037,
    "seller_zip_prefix": 20040,
    "product_weight_g": 500,
    "product_length_cm": 20,
    "product_height_cm": 10,
    "product_width_cm": 15,
    "price": 80,
    "quantity": 1,
    "category": None,
}


def capture() -> dict:
    """Return the answers a user would see, from freshly loaded packages and data."""
    services = Services(store=Store(log_predictions=False))
    options = services.forecast_options()
    queue = services.review_queue(20)
    sellers = services.sellers_at_risk(20, alerts_only=True)
    return {
        "loaded": sorted(services.predictors),
        "freight": services.freight(FREIGHT_REQUEST),
        "delivery": [services.delivery_days(state)["predicted_days"] for state in ("SP", "AM")],
        "forecast_options": options,
        "daily": [
            row["predicted_orders"]
            for row in services.daily_forecast(options["latest_daily_date"], 1)
        ],
        "category": [
            services.category_forecast(options["latest_week_end"], category)["predicted_items"]
            for category in options["categories"]
        ],
        "review_queue": [(row["order_id"], row["risk_score"]) for row in queue["orders"]],
        "reviews_in_window": queue["orders_in_window"],
        "sellers": [(row["seller_id"], row["risk_score"]) for row in sellers["sellers"]],
        "seller_alerts": sellers["alerts_in_snapshot"],
    }


def differences(before, after, path="answers") -> list[str]:
    """Return every place the two captures disagree."""
    if isinstance(before, dict) and isinstance(after, dict):
        found = []
        for key in sorted(set(before) | set(after), key=str):
            found += differences(before.get(key), after.get(key), f"{path}.{key}")
        return found
    if isinstance(before, (list, tuple)) and isinstance(after, (list, tuple)):
        if len(before) != len(after):
            return [f"{path}: {len(before)} items before, {len(after)} after"]
        found = []
        for index, (old, new) in enumerate(zip(before, after, strict=True)):
            found += differences(old, new, f"{path}[{index}]")
        return found
    if isinstance(before, float) and isinstance(after, float):
        return (
            []
            if math.isclose(before, after, rel_tol=0, abs_tol=1e-9)
            else [f"{path}: {before} became {after}"]
        )
    return [] if before == after else [f"{path}: {before!r} became {after!r}"]


def main() -> int:
    if not config.DATABASE_PATH.is_file():
        print("Nothing to compare with. Build the project once first.")
        return 1

    registry = config.REPORTS_DIR / "model_registry.json"
    registry_text = registry.read_text()

    before = capture()
    for step in BUILD_STEPS:
        started = time.monotonic()
        print(f"Running {step}…", flush=True)
        subprocess.run(
            [sys.executable, "-W", "ignore", "-m", step], check=True, capture_output=True
        )
        print(f"  done in {time.monotonic() - started:.0f}s", flush=True)
    after = capture()
    registry.write_text(registry_text)

    found = differences(before, after)
    if found:
        print(f"Rebuild changed {len(found)} answers:")
        for line in found[:20]:
            print(f"  {line}")
        return 1
    print("Rebuild reproduced every answer exactly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
