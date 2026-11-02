"""Build one feature table per problem from the processed tables.

Every feature uses only what was known at the row's prediction moment. Encoding
and scaling are left to model pipelines, so they're fitted on training rows only.
"""

import pandas as pd

from src.data.preprocess import FAILED_STATUSES, clean_orders
from src.features.common import (
    brazil_holidays,
    days_between,
    haversine_km,
    past_totals,
    peak_window_days,
    safe_rate,
    smoothed_rate,
    window_totals,
)

RECENT_DAYS = 30
LOAD_DAYS = 7

# Problem 3 forecasts 28 days ahead and problem 5 forecasts 4 weeks ahead, so
# every lag must be at least that old to be available at forecast time.
DAILY_HORIZON = 28
WEEKLY_HORIZON = 4

ORDER_NUMERIC = [
    "distance_km",
    "same_state",
    "days_promised",
    "purchase_hour",
    "purchase_day_of_week",
    "is_weekend",
    "n_items",
    "n_sellers",
    "item_total",
    "freight_total",
    "freight_ratio",
    "total_weight_g",
    "payment_installments",
]
ORDER_HISTORY = [
    "seller_past_orders",
    "seller_late_rate",
    "seller_mean_days",
    "route_late_rate",
    "route_mean_days",
    "recent_late_rate",
    "recent_mean_days",
    "recent_orders",
]
ORDER_CATEGORICAL = ["customer_state", "seller_state", "main_category", "payment_type"]

# The columns each model may use. Problems 1 and 4 share the delivery table.
FEATURES = {
    "delivery": {
        "numeric": ORDER_NUMERIC + ORDER_HISTORY,
        "categorical": ORDER_CATEGORICAL,
    },
    "reviews": {
        "numeric": ORDER_NUMERIC
        + ORDER_HISTORY
        + [
            "is_overdue",
            "days_to_moment",
            "days_ahead_of_promise",
            "approval_hours",
            "days_to_carrier",
            "seller_past_reviews",
            "seller_low_rate",
            "category_low_rate",
            "recent_low_rate",
        ],
        "categorical": ORDER_CATEGORICAL,
    },
    "daily_orders": {
        "numeric": [
            "lag_28",
            "lag_35",
            "lag_42",
            "mean_7_lag_28",
            "mean_28_lag_28",
            "day_of_week",
            "is_weekend",
            "is_holiday",
            "is_peak_window",
            "days_since_start",
        ],
        "categorical": [],
    },
    "weekly_category": {
        "numeric": [
            "lag_4",
            "lag_5",
            "lag_6",
            "mean_4_lag_4",
            "has_holiday",
            "is_peak_week",
            "weeks_since_start",
        ],
        "categorical": ["category"],
    },
    "seller_snapshots": {
        "numeric": [
            "sales_30d",
            "sales_90d",
            "sales_total",
            "revenue_90d",
            "recent_sales_share",
            "days_since_last_sale",
            "tenure_days",
            "seller_late_rate",
            "seller_low_rate",
        ],
        "categorical": ["seller_state"],
    },
    "freight": {
        "numeric": [
            "distance_km",
            "same_state",
            "product_weight_g",
            "volume_cm3",
            "longest_side_cm",
            "price",
            "quantity",
        ],
        "categorical": ["customer_state", "seller_state", "category"],
    },
}


def add_location_features(table: pd.DataFrame) -> pd.DataFrame:
    """Add the distance between seller and customer, and whether they share a state."""
    table = table.copy()
    table["distance_km"] = haversine_km(
        table["customer_lat"], table["customer_lng"], table["seller_lat"], table["seller_lng"]
    )
    table["same_state"] = (table["customer_state"] == table["seller_state"]).astype(int)
    return table


def add_order_history(table: pd.DataFrame, daily_orders: pd.DataFrame) -> pd.DataFrame:
    """Add seller, route, and recent platform history as of each purchase."""
    table = table.copy()
    purchase = table["order_purchase_timestamp"]
    known_at = table["outcome_date"]
    route = table["seller_state"] + ">" + table["customer_state"]
    sellers = table["seller_id"]

    # Overall rates are the prior that small groups are pulled towards.
    late_prior = safe_rate(past_totals(purchase, known_at, table["is_late"]))
    days_prior = safe_rate(past_totals(purchase, known_at, table["days_to_deliver"]))

    seller_late = past_totals(purchase, known_at, table["is_late"], sellers, sellers)
    seller_days = past_totals(purchase, known_at, table["days_to_deliver"], sellers, sellers)
    route_late = past_totals(purchase, known_at, table["is_late"], route, route)
    route_days = past_totals(purchase, known_at, table["days_to_deliver"], route, route)

    table["seller_past_orders"] = seller_late["count"]
    table["seller_late_rate"] = smoothed_rate(seller_late, late_prior)
    table["seller_mean_days"] = smoothed_rate(seller_days, days_prior)
    table["route_late_rate"] = smoothed_rate(route_late, late_prior)
    table["route_mean_days"] = smoothed_rate(route_days, days_prior)

    table["recent_late_rate"] = safe_rate(
        window_totals(purchase, RECENT_DAYS, known_at, table["is_late"])
    )
    table["recent_mean_days"] = safe_rate(
        window_totals(purchase, RECENT_DAYS, known_at, table["days_to_deliver"])
    )

    # A day's order count is complete once that day has ended.
    day_complete = daily_orders["date"] + pd.Timedelta(days=1)
    table["recent_orders"] = window_totals(
        purchase, LOAD_DAYS, day_complete, daily_orders["orders"]
    )["total"]
    return table


def build_delivery_features(delivery, daily_orders) -> pd.DataFrame:
    """Return features for problems 1 and 4, known at purchase."""
    table = add_location_features(delivery)
    purchase = table["order_purchase_timestamp"]

    table["days_promised"] = days_between(purchase, table["order_estimated_delivery_date"])
    table["purchase_hour"] = purchase.dt.hour
    table["purchase_day_of_week"] = purchase.dt.day_of_week
    table["is_weekend"] = (purchase.dt.day_of_week >= 5).astype(int)
    table["freight_ratio"] = table["freight_total"] / table["item_total"]
    table["is_late"] = table["is_late"].astype(int)
    return add_order_history(table, daily_orders)


def build_review_features(reviews, delivery_features) -> pd.DataFrame:
    """Return features for problem 2, known at the prediction moment."""
    shared = ["order_id", *ORDER_NUMERIC, *ORDER_HISTORY]
    table = reviews.drop(
        columns=[c for c in shared if c in reviews.columns and c != "order_id"]
    ).merge(delivery_features[shared], on="order_id")

    moment = table["prediction_moment"]
    purchase = table["order_purchase_timestamp"]
    promise_end = table["order_estimated_delivery_date"] + pd.Timedelta(days=1)

    table["is_overdue"] = table["is_overdue"].astype(int)
    table["is_low"] = table["is_low"].astype(int)
    table["days_to_moment"] = days_between(purchase, moment)
    table["days_ahead_of_promise"] = days_between(moment, promise_end)
    table["approval_hours"] = days_between(purchase, table["order_approved_at"]) * 24
    table["days_to_carrier"] = days_between(purchase, table["order_delivered_carrier_date"])

    # A score only counts once the customer has answered.
    known_at = table["score_known_date"]
    low_prior = safe_rate(past_totals(moment, known_at, table["is_low"]))
    sellers = table["seller_id"]
    categories = table["main_category"].fillna("unknown")
    seller_low = past_totals(moment, known_at, table["is_low"], sellers, sellers)
    category_low = past_totals(moment, known_at, table["is_low"], categories, categories)

    table["seller_past_reviews"] = seller_low["count"]
    table["seller_low_rate"] = smoothed_rate(seller_low, low_prior)
    table["category_low_rate"] = smoothed_rate(category_low, low_prior)
    table["recent_low_rate"] = safe_rate(
        window_totals(moment, RECENT_DAYS, known_at, table["is_low"])
    )
    return table


def add_calendar_flags(table, date_column, years) -> pd.DataFrame:
    """Add day-level calendar columns, which are known in advance."""
    table = table.copy()
    dates = table[date_column]
    public_holidays = brazil_holidays(years)
    table["day_of_week"] = dates.dt.day_of_week
    table["is_weekend"] = (dates.dt.day_of_week >= 5).astype(int)
    table["is_holiday"] = dates.isin(public_holidays).astype(int)
    table["is_peak_window"] = dates.isin(peak_window_days(years)).astype(int)
    return table


def build_daily_features(daily_orders) -> pd.DataFrame:
    """Return features for problem 3, with every lag at least 28 days old."""
    table = daily_orders.sort_values("date").reset_index(drop=True)
    table = add_calendar_flags(table, "date", sorted(table["date"].dt.year.unique()))

    # The surge would otherwise echo through lags for weeks, so lags see the
    # week before it instead. The target keeps the real value.
    orders = table["orders"].where(table["is_peak_window"] == 0, table["orders"].shift(7))
    table["lag_28"] = orders.shift(DAILY_HORIZON)
    table["lag_35"] = orders.shift(DAILY_HORIZON + 7)
    table["lag_42"] = orders.shift(DAILY_HORIZON + 14)
    table["mean_7_lag_28"] = orders.shift(DAILY_HORIZON).rolling(7).mean()
    table["mean_28_lag_28"] = orders.shift(DAILY_HORIZON).rolling(28).mean()
    table["days_since_start"] = (table["date"] - table["date"].min()).dt.days
    return table


def build_weekly_features(weekly_category) -> pd.DataFrame:
    """Return features for problem 5, with every lag at least 4 weeks old."""
    table = weekly_category.sort_values(["category", "week_end"]).reset_index(drop=True)
    years = sorted(table["week_end"].dt.year.unique())

    def week_contains(days):
        marked = pd.Series(pd.to_datetime(sorted(days)))
        week_ends = marked.dt.to_period("W-SUN").dt.end_time.dt.normalize()
        return table["week_end"].isin(week_ends).astype(int)

    table["has_holiday"] = week_contains(brazil_holidays(years))
    table["is_peak_week"] = week_contains(peak_window_days(years))

    # As with daily lags, peak weeks are replaced by the last normal week.
    normal_items = table["items"].where(table["is_peak_week"] == 0)
    by_category = normal_items.groupby(table["category"]).ffill().groupby(table["category"])

    table["lag_4"] = by_category.shift(WEEKLY_HORIZON)
    table["lag_5"] = by_category.shift(WEEKLY_HORIZON + 1)
    table["lag_6"] = by_category.shift(WEEKLY_HORIZON + 2)
    table["mean_4_lag_4"] = by_category.transform(
        lambda items: items.shift(WEEKLY_HORIZON).rolling(4).mean()
    )
    table["weeks_since_start"] = (table["week_end"] - table["week_end"].min()).dt.days // 7
    return table


def build_sales(items, orders) -> pd.DataFrame:
    """Return completed item sales with their purchase dates."""
    placed = clean_orders(orders)
    placed = placed[~placed["order_status"].isin(FAILED_STATUSES)]
    sales = items[["order_id", "seller_id", "price"]].merge(
        placed[["order_id", "order_purchase_timestamp"]], on="order_id"
    )
    return sales.rename(columns={"order_purchase_timestamp": "sale_date"})


def build_seller_features(snapshots, sales, delivery_features, review_features) -> pd.DataFrame:
    """Return features for problem 6, using only activity before each snapshot."""
    parts = []
    for date, group in snapshots.groupby("snapshot_date"):
        before = sales[sales["sale_date"] < date]
        grouped = before.groupby("seller_id")
        stats = grouped.agg(
            sales_total=("order_id", "nunique"),
            first_sale=("sale_date", "min"),
            last_sale=("sale_date", "max"),
        )
        for days in (30, 90):
            recent = before[before["sale_date"] >= date - pd.Timedelta(days=days)]
            stats[f"sales_{days}d"] = recent.groupby("seller_id")["order_id"].nunique()
            if days == 90:
                stats["revenue_90d"] = recent.groupby("seller_id")["price"].sum()
        parts.append(group.join(stats, on="seller_id"))

    table = pd.concat(parts, ignore_index=True)
    snapshot_date = table["snapshot_date"]
    table["sales_30d"] = table["sales_30d"].fillna(0)
    table["recent_sales_share"] = table["sales_30d"] / table["sales_90d"]
    table["days_since_last_sale"] = days_between(table["last_sale"], snapshot_date)
    table["tenure_days"] = days_between(table["first_sale"], snapshot_date)

    sellers = table["seller_id"]
    late_history = past_totals(
        snapshot_date,
        delivery_features["outcome_date"],
        delivery_features["is_late"],
        sellers,
        delivery_features["seller_id"],
    )
    low_history = past_totals(
        snapshot_date,
        review_features["score_known_date"],
        review_features["is_low"],
        sellers,
        review_features["seller_id"],
    )
    table["seller_late_rate"] = safe_rate(late_history)
    table["seller_low_rate"] = safe_rate(low_history)
    table["is_inactive"] = table["is_inactive"].astype(int)
    return table.drop(columns=["first_sale", "last_sale"])


def build_freight_features(freight) -> pd.DataFrame:
    """Return features for problem 7, known at checkout."""
    table = add_location_features(freight)
    sides = table[["product_length_cm", "product_height_cm", "product_width_cm"]]
    table["volume_cm3"] = sides.prod(axis=1, skipna=False)
    table["longest_side_cm"] = sides.max(axis=1)
    return table


def build_all_features(processed: dict[str, pd.DataFrame], raw) -> dict[str, pd.DataFrame]:
    """Build every feature table."""
    delivery = build_delivery_features(processed["delivery"], processed["daily_orders"])
    reviews = build_review_features(processed["reviews"], delivery)
    sales = build_sales(raw["order_items"], raw["orders"])

    return {
        "delivery": delivery,
        "reviews": reviews,
        "daily_orders": build_daily_features(processed["daily_orders"]),
        "weekly_category": build_weekly_features(processed["weekly_category"]),
        "seller_snapshots": build_seller_features(
            processed["seller_snapshots"], sales, delivery, reviews
        ),
        "freight": build_freight_features(processed["freight"]),
    }
