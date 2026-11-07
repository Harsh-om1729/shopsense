"""Connect the API to packaged models and the database."""

from datetime import date
from pathlib import Path

import pandas as pd

from src import config
from src.db.store import Store
from src.features.build import build_freight_features
from src.models.predictor import (
    InvalidInputError,
    ModelNotAvailableError,
    load_predictor,
    read_metadata,
)

FREIGHT = "freight_cost"
LOW_REVIEW = "low_review_risk"
SELLER = "seller_inactivity_risk"
DAILY = "daily_orders_rule"
DELIVERY = "delivery_time_rule"
CATEGORY = "category_demand_rule"
LATE_DELIVERY = "late_delivery_risk"
PACKAGES = [FREIGHT, LOW_REVIEW, SELLER, DAILY, DELIVERY, CATEGORY, LATE_DELIVERY]

OPTIONAL_FREIGHT_NUMBERS = [
    "customer_lat",
    "customer_lng",
    "seller_lat",
    "seller_lng",
    "product_weight_g",
    "product_length_cm",
    "product_height_cm",
    "product_width_cm",
]

REVIEW_WINDOW_DAYS = 7
DELIVERY_NOTE = "An estimate only. Keep Olist's promised date for customers."


def optional_number(value):
    """Return a float, or None for a missing value, which JSON can't hold as NaN."""
    return None if pd.isna(value) else float(value)


class Services:
    """Hold the loaded packages and answer each endpoint's question."""

    def __init__(self, models_dir: Path = config.MODELS_DIR, store: Store | None = None):
        self.models_dir = models_dir
        self.store = store or Store()
        self.predictors = {}
        self.unavailable = {}
        for name in PACKAGES:
            try:
                self.predictors[name] = load_predictor(name, models_dir)
            except ModelNotAvailableError as error:
                self.unavailable[name] = str(error)

    def predictor(self, name: str):
        """Return a loaded package, or raise with the reason it isn't available."""
        if name not in self.predictors:
            raise ModelNotAvailableError(self.unavailable.get(name, f"{name} isn't loaded."))
        return self.predictors[name]

    def database_ready(self) -> bool:
        return self.store.ready()

    def log(self, name: str, inputs, outputs) -> None:
        """Record a served prediction with the version that made it."""
        version = self.predictors[name].metadata["version"]
        self.store.record(name, version, inputs, outputs)

    def models(self) -> list[dict]:
        """Return each package's status and Phase 7 verdict."""
        listed = []
        for name in PACKAGES:
            try:
                metadata = read_metadata(name, self.models_dir)
            except ModelNotAvailableError:
                continue
            listed.append(
                {
                    "name": name,
                    "problem": metadata["problem"],
                    "status": metadata["status"],
                    "kind": metadata.get("kind"),
                    "version": metadata["version"],
                    "verdict": metadata["holdout"]["verdict"],
                    "note": metadata.get("note") or metadata.get("reason"),
                }
            )
        return listed

    def with_coordinates(self, request: dict) -> dict:
        """Replace zip prefixes with coordinates, leaving unknown ones missing."""
        resolved = dict(request)
        for party in ("customer", "seller"):
            prefix = resolved.pop(f"{party}_zip_prefix", None)
            coordinates = None if prefix is None else self.store.coordinates_for_zip(prefix)
            if coordinates is not None:
                resolved[f"{party}_lat"], resolved[f"{party}_lng"] = coordinates
        return resolved

    def freight(self, request: dict) -> dict:
        """Build features with the training code, then predict."""
        predictor = self.predictor(FREIGHT)
        resolved = self.with_coordinates(request)

        # Optional fields can be None, and floats turn them into NaN for the model.
        columns = {column: "float" for column in OPTIONAL_FREIGHT_NUMBERS}
        rows = pd.DataFrame([resolved]).astype({**columns, "category": "object"})
        features = build_freight_features(rows)
        predicted = predictor.predict(features)

        result = {
            "predicted_freight": float(predicted["predicted_freight"].iloc[0]),
            "distance_known": bool(features["distance_km"].notna().iloc[0]),
        }
        self.log(FREIGHT, request, result)
        return result

    def delivery_days(self, customer_state: str) -> dict:
        rows = pd.DataFrame({"customer_state": [customer_state]})
        predicted = self.predictor(DELIVERY).predict(rows)
        result = {
            "customer_state": customer_state,
            "predicted_days": float(predicted["predicted_days"].iloc[0]),
            "note": DELIVERY_NOTE,
        }
        self.log(DELIVERY, {"customer_state": customer_state}, result)
        return result

    def daily_forecast(self, start: date, days: int) -> list[dict]:
        dates = pd.date_range(start, periods=days, freq="D")
        predicted = self.predictor(DAILY).predict(pd.DataFrame({"date": dates}))
        result = [
            {"date": day.date(), "predicted_orders": float(value)}
            for day, value in zip(dates, predicted["predicted_orders"], strict=True)
        ]
        self.log(DAILY, {"start": start, "days": days}, result)
        return result

    def forecast_options(self) -> dict:
        """Return what the forecast rules can answer, so clients don't guess."""
        daily = self.predictor(DAILY)
        weekly = self.predictor(CATEGORY)
        return {
            "data_end_date": daily.data_end().date(),
            "latest_daily_date": daily.latest_date().date(),
            "latest_week_end": weekly.latest_week_end().date(),
            "categories": weekly.categories(),
        }

    def category_forecast(self, week_end: date, category: str) -> dict:
        rows = pd.DataFrame({"week_end": [week_end], "category": [category]})
        predicted = self.predictor(CATEGORY).predict(rows)
        result = {
            "week_end": week_end,
            "category": category,
            "predicted_items": float(predicted["predicted_items"].iloc[0]),
        }
        self.log(CATEGORY, {"week_end": week_end, "category": category}, result)
        return result

    def review_queue(self, limit: int) -> dict:
        """Rank the most recent orders by low-review risk."""
        predictor = self.predictor(LOW_REVIEW)
        window_start, window_end, rows = self.store.recent_reviews(REVIEW_WINDOW_DAYS)
        if rows.empty:
            raise InvalidInputError("No orders in the review window.")

        ranked = rows.join(predictor.predict(rows)).sort_values("rank").head(limit)
        result = {
            "window_start": window_start.date(),
            "window_end": window_end.date(),
            "orders_in_window": len(rows),
            "scored_on_training_data": True,
            "orders": [
                {
                    "rank": int(row.rank),
                    "order_id": row.order_id,
                    "risk_score": float(row.risk_score),
                    "is_overdue": bool(row.is_overdue),
                    "customer_state": row.customer_state,
                    "seller_id": row.seller_id,
                }
                for row in ranked.itertuples()
            ],
        }
        summary = {"orders_in_window": len(rows), "returned": len(ranked)}
        self.log(LOW_REVIEW, {"limit": limit}, summary)
        return result

    def sellers_at_risk(self, limit: int, alerts_only: bool) -> dict:
        """Return the latest snapshot's riskiest sellers."""
        predictor = self.predictor(SELLER)
        snapshot, rows = self.store.latest_seller_snapshot()

        scored = rows.join(predictor.predict(rows))
        shown = scored[scored["is_alert"]] if alerts_only else scored
        shown = shown.sort_values("risk_score", ascending=False).head(limit)
        alerts = int(scored["is_alert"].sum())
        result = {
            "snapshot_date": snapshot.date(),
            "sellers_in_snapshot": len(rows),
            "alerts_in_snapshot": alerts,
            "scored_on_training_data": True,
            "sellers": [
                {
                    "seller_id": row.seller_id,
                    "seller_state": None if pd.isna(row.seller_state) else row.seller_state,
                    "risk_score": float(row.risk_score),
                    "is_alert": bool(row.is_alert),
                    "days_since_last_sale": float(row.days_since_last_sale),
                    "revenue_90d": optional_number(row.revenue_90d),
                }
                for row in shown.itertuples()
            ],
        }
        summary = {"sellers_in_snapshot": len(rows), "alerts": alerts, "returned": len(shown)}
        self.log(SELLER, {"limit": limit, "alerts_only": alerts_only}, summary)
        return result

    def late_delivery(self) -> None:
        """Raise the reason this model is held. It never returns a prediction."""
        self.predictor(LATE_DELIVERY)
