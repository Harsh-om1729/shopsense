"""Turn raw Olist tables into one clean table per problem.

Everything here is a fixed rule. Steps that learn from data, such as filling
missing values with a median, belong in model pipelines so they are fitted on
training rows only.
"""

import numpy as np
import pandas as pd

from src import config

# Approximate bounds of Brazil, used to drop impossible coordinates.
LAT_BOUNDS = (-34, 6)
LNG_BOUNDS = (-74, -34)

TOP_CATEGORY_COUNT = 10
SELLER_LOOKBACK_DAYS = 90
SELLER_INACTIVE_DAYS = 60
FAILED_STATUSES = ["canceled", "unavailable"]

# Columns known when an order is placed.
PURCHASE_COLUMNS = [
    "order_id",
    "order_purchase_timestamp",
    "order_estimated_delivery_date",
    "customer_state",
    "customer_lat",
    "customer_lng",
    "seller_id",
    "seller_state",
    "seller_lat",
    "seller_lng",
    "n_items",
    "n_sellers",
    "item_total",
    "freight_total",
    "total_weight_g",
    "main_category",
    "payment_type",
    "payment_installments",
    "payment_value_total",
]

# Columns that only exist after the prediction moment for problems 1 and 4.
POST_PURCHASE_COLUMNS = [
    "order_status",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
]

# Never use these as features. They hold the answer or the time it was known.
TARGET_COLUMNS = {
    "delivery": ["is_late", "days_to_deliver", "outcome_date", "period"],
    "reviews": ["is_low", "review_score", "outcome_date", "period"],
    "seller_snapshots": ["is_inactive", "outcome_date", "period"],
    "freight": ["freight_value", "period"],
}


def assign_period(event_date, outcome_date=None, embargo_days=config.EMBARGO_DAYS):
    """Label each row as development, embargo, or holdout.

    A row is embargoed if it falls just before the holdout, or if its outcome
    was unknown when the holdout began.
    """
    holdout_start = pd.Timestamp(config.HOLDOUT_START)
    embargo_start = holdout_start - pd.Timedelta(days=embargo_days)
    outcome = event_date if outcome_date is None else outcome_date

    in_holdout = event_date >= holdout_start
    in_embargo = (event_date >= embargo_start) | (outcome >= holdout_start)
    labels = np.select([in_holdout, in_embargo], ["holdout", "embargo"], default="development")
    return pd.Series(labels, index=event_date.index, dtype="str")


def clean_orders(orders: pd.DataFrame) -> pd.DataFrame:
    """Keep orders in the usable date range and clear impossible carrier dates."""
    last_moment = pd.Timestamp(config.LAST_ORDER_DATE) + pd.Timedelta(days=1)
    purchase = orders["order_purchase_timestamp"]
    keep = (purchase >= config.FIRST_ORDER_DATE) & (purchase < last_moment)
    cleaned = orders[keep].copy()

    carrier = cleaned["order_delivered_carrier_date"]
    impossible = (carrier < cleaned["order_purchase_timestamp"]) | (
        carrier > cleaned["order_delivered_customer_date"]
    )
    cleaned.loc[impossible, "order_delivered_carrier_date"] = pd.NaT
    return cleaned


def clean_zip_coordinates(geolocation: pd.DataFrame) -> pd.DataFrame:
    """Return one median coordinate per zip prefix, ignoring points outside Brazil."""
    in_brazil = geolocation["geolocation_lat"].between(*LAT_BOUNDS) & geolocation[
        "geolocation_lng"
    ].between(*LNG_BOUNDS)
    coords = (
        geolocation[in_brazil]
        .groupby("geolocation_zip_code_prefix")[["geolocation_lat", "geolocation_lng"]]
        .median()
    )
    coords.columns = ["lat", "lng"]
    return coords


def clean_products(products: pd.DataFrame, translation: pd.DataFrame) -> pd.DataFrame:
    """Fix column names, add English categories, and blank impossible weights."""
    cleaned = products.rename(
        columns={
            "product_name_lenght": "product_name_length",
            "product_description_lenght": "product_description_length",
        }
    ).merge(translation, on="product_category_name", how="left")

    # Two categories have no translation, so keep their Portuguese names.
    cleaned["category"] = (
        cleaned["product_category_name_english"]
        .fillna(cleaned["product_category_name"])
        .fillna("unknown")
    )
    cleaned["product_weight_g"] = cleaned["product_weight_g"].where(cleaned["product_weight_g"] > 0)
    return cleaned.drop(columns=["product_category_name", "product_category_name_english"])


def summarise_payments(payments: pd.DataFrame) -> pd.DataFrame:
    """Return one payment row per order, using the largest payment's type."""
    summary = payments.groupby("order_id").agg(
        payment_value_total=("payment_value", "sum"),
        payment_installments=("payment_installments", "max"),
    )
    # Zero instalments is impossible, since every payment has at least one.
    summary["payment_installments"] = summary["payment_installments"].clip(lower=1)

    largest_first = payments.sort_values(
        ["order_id", "payment_value", "payment_sequential"], ascending=[True, False, True]
    )
    main_type = largest_first.drop_duplicates("order_id").set_index("order_id")["payment_type"]
    summary["payment_type"] = main_type.replace("not_defined", "unknown")
    return summary


def summarise_items(items: pd.DataFrame, products: pd.DataFrame) -> pd.DataFrame:
    """Return one item row per order, naming the most expensive item as the main one."""
    with_products = items.merge(
        products[["product_id", "category", "product_weight_g"]], on="product_id", how="left"
    )
    summary = with_products.groupby("order_id").agg(
        n_items=("order_item_id", "size"),
        n_sellers=("seller_id", "nunique"),
        item_total=("price", "sum"),
        freight_total=("freight_value", "sum"),
    )
    summary["total_weight_g"] = with_products.groupby("order_id")["product_weight_g"].sum(
        min_count=1
    )

    largest_first = with_products.sort_values(
        ["order_id", "price", "order_item_id"], ascending=[True, False, True]
    )
    main_item = largest_first.drop_duplicates("order_id").set_index("order_id")
    summary["seller_id"] = main_item["seller_id"]
    summary["main_category"] = main_item["category"]
    return summary


def latest_reviews(reviews: pd.DataFrame) -> pd.DataFrame:
    """Keep one review per order, the most recently answered."""
    ordered = reviews.sort_values("review_answer_timestamp")
    return ordered.drop_duplicates("order_id", keep="last")


def add_coordinates(df, coords, zip_column, prefix):
    """Join latitude and longitude for a zip column."""
    named = coords.add_prefix(f"{prefix}_")
    return df.join(named, on=zip_column)


def build_order_base(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Return one row per usable order with its customer, items, seller, and payment."""
    orders = clean_orders(tables["orders"])
    products = clean_products(tables["products"], tables["category_translation"])
    coords = clean_zip_coordinates(tables["geolocation"])

    customers = tables["customers"][["customer_id", "customer_state", "customer_zip_code_prefix"]]
    sellers = tables["sellers"][["seller_id", "seller_state", "seller_zip_code_prefix"]]

    base = (
        orders.merge(customers, on="customer_id", how="left")
        .join(summarise_items(tables["order_items"], products), on="order_id")
        .join(summarise_payments(tables["order_payments"]), on="order_id")
        .merge(sellers, on="seller_id", how="left")
    )
    base = add_coordinates(base, coords, "customer_zip_code_prefix", "customer")
    base = add_coordinates(base, coords, "seller_zip_code_prefix", "seller")

    if not base["order_id"].is_unique:
        raise ValueError("Order base must have one row per order.")
    return base


def build_delivery_table(base: pd.DataFrame) -> pd.DataFrame:
    """Return the table for problems 1 and 4, using only purchase-time columns."""
    delivered_date = base["order_delivered_customer_date"]
    mask = base["order_status"].eq("delivered") & delivered_date.notna()
    table = base.loc[mask, PURCHASE_COLUMNS].copy()

    outcome = delivered_date[mask]
    table["is_late"] = outcome.dt.normalize() > table["order_estimated_delivery_date"]
    table["days_to_deliver"] = (
        outcome - table["order_purchase_timestamp"]
    ).dt.total_seconds() / 86400
    table["outcome_date"] = outcome
    table["period"] = assign_period(table["order_purchase_timestamp"], outcome)
    return table.reset_index(drop=True)


def build_review_table(base: pd.DataFrame, reviews: pd.DataFrame) -> pd.DataFrame:
    """Return the table for problem 2, using columns known at the prediction moment.

    Olist's survey usually goes out a day after delivery or the promised date,
    whichever comes first, so a late order is often reviewed before it arrives.
    The prediction moment is therefore the delivery or the end of the promised
    day, whichever comes first.
    """
    delivered_date = base["order_delivered_customer_date"]
    mask = base["order_status"].eq("delivered") & delivered_date.notna()
    columns = PURCHASE_COLUMNS + [
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
    ]
    table = base.loc[mask, columns].merge(
        latest_reviews(reviews)[["order_id", "review_score", "review_creation_date"]],
        on="order_id",
    )

    delivered = table.pop("order_delivered_customer_date")
    promise_end = table["order_estimated_delivery_date"] + pd.Timedelta(days=1)
    is_overdue = delivered >= promise_end
    moment = delivered.where(~is_overdue, promise_end)
    table["prediction_moment"] = moment
    table["is_overdue"] = is_overdue

    # Hide anything that happened after the prediction moment.
    table["delivered_date"] = delivered.where(~is_overdue)
    for column in ["order_approved_at", "order_delivered_carrier_date"]:
        table[column] = table[column].where(table[column] <= moment)

    # A review written before the moment can't be predicted from it.
    table = table[table["review_creation_date"] >= moment.dt.normalize()].copy()

    table["is_low"] = table["review_score"] <= 2
    table["outcome_date"] = table.pop("review_creation_date")
    table["period"] = assign_period(table["order_purchase_timestamp"], table["outcome_date"])
    return table.reset_index(drop=True)


def build_daily_orders(orders: pd.DataFrame) -> pd.DataFrame:
    """Return orders placed per day with no missing days, for problem 3."""
    day = orders["order_purchase_timestamp"].dt.normalize()
    all_days = pd.date_range(day.min(), config.LAST_ORDER_DATE, freq="D", name="date")
    counts = day.value_counts().reindex(all_days, fill_value=0).rename("orders").reset_index()
    counts["period"] = assign_period(counts["date"], embargo_days=0)
    return counts


def build_weekly_category(items, orders, products) -> pd.DataFrame:
    """Return complete Monday-to-Sunday item counts for the top categories, for problem 5."""
    sold = items.merge(orders[["order_id", "order_purchase_timestamp"]], on="order_id").merge(
        products[["product_id", "category"]], on="product_id", how="left"
    )
    sold["week_end"] = sold["order_purchase_timestamp"].dt.to_period("W-SUN").dt.end_time
    sold["week_end"] = sold["week_end"].dt.normalize()

    # Choose categories from the development period so the holdout has no say.
    is_development = sold["order_purchase_timestamp"] < config.HOLDOUT_START
    known = sold.loc[is_development & sold["category"].ne("unknown"), "category"]
    top_categories = known.value_counts().head(TOP_CATEGORY_COUNT).index

    first_day = orders["order_purchase_timestamp"].min().normalize()
    weeks = pd.date_range(
        first_day + pd.Timedelta(days=6), config.LAST_ORDER_DATE, freq="W-SUN", name="week_end"
    )
    grid = pd.MultiIndex.from_product([weeks, top_categories], names=["week_end", "category"])
    table = (
        sold[sold["category"].isin(top_categories)]
        .groupby(["week_end", "category"])
        .size()
        .reindex(grid, fill_value=0)
        .rename("items")
        .reset_index()
    )
    table["period"] = assign_period(table["week_end"], embargo_days=0)
    return table


def build_seller_snapshots(items, orders, sellers) -> pd.DataFrame:
    """Return one row per recently active seller per month, for problem 6."""
    placed = orders[~orders["order_status"].isin(FAILED_STATUSES)]
    sales = items[["order_id", "seller_id"]].merge(
        placed[["order_id", "order_purchase_timestamp"]], on="order_id"
    )
    sale_date = sales["order_purchase_timestamp"]
    lookback = pd.Timedelta(days=SELLER_LOOKBACK_DAYS)
    horizon = pd.Timedelta(days=SELLER_INACTIVE_DAYS)

    # Each snapshot needs a full lookback before it and a full horizon after it.
    first_snapshot = pd.Timestamp(config.FIRST_ORDER_DATE) + lookback
    last_snapshot = pd.Timestamp(config.LAST_ORDER_DATE) - horizon
    snapshots = []
    for date in pd.date_range(first_snapshot, last_snapshot, freq="MS"):
        recent = (sale_date >= date - lookback) & (sale_date < date)
        future = (sale_date >= date) & (sale_date < date + horizon)
        active = sales.loc[recent, "seller_id"].drop_duplicates()
        returning = set(sales.loc[future, "seller_id"])
        snapshots.append(
            pd.DataFrame(
                {
                    "snapshot_date": date,
                    "seller_id": active,
                    "is_inactive": ~active.isin(returning),
                    "outcome_date": date + horizon,
                }
            )
        )

    table = pd.concat(snapshots, ignore_index=True).merge(
        sellers[["seller_id", "seller_state"]], on="seller_id", how="left"
    )
    table["period"] = assign_period(table["snapshot_date"], table["outcome_date"])
    return table


def build_freight_table(items, base, products, sellers) -> pd.DataFrame:
    """Return one row per product per order, for problem 7.

    Repeats of a product in an order have identical freight, so they become a
    quantity instead of exact duplicate rows.
    """
    grouped = items.groupby(["order_id", "product_id", "seller_id"], as_index=False).agg(
        quantity=("order_item_id", "size"),
        price=("price", "first"),
        freight_value=("freight_value", "first"),
    )
    product_columns = [
        "product_id",
        "category",
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
    ]
    order_columns = [
        "order_id",
        "order_purchase_timestamp",
        "customer_state",
        "customer_lat",
        "customer_lng",
    ]
    table = (
        grouped.merge(base[order_columns], on="order_id")
        .merge(products[product_columns], on="product_id", how="left")
        .merge(sellers, on="seller_id", how="left")
    )
    table["period"] = assign_period(table["order_purchase_timestamp"], embargo_days=0)
    return table


def build_all(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Build every processed table from the raw tables."""
    base = build_order_base(tables)
    orders = clean_orders(tables["orders"])
    products = clean_products(tables["products"], tables["category_translation"])
    items = tables["order_items"]
    coords = clean_zip_coordinates(tables["geolocation"])
    sellers = add_coordinates(tables["sellers"], coords, "seller_zip_code_prefix", "seller")[
        ["seller_id", "seller_state", "seller_lat", "seller_lng"]
    ]

    return {
        "delivery": build_delivery_table(base),
        "reviews": build_review_table(base, tables["order_reviews"]),
        "daily_orders": build_daily_orders(orders),
        "weekly_category": build_weekly_category(items, orders, products),
        "seller_snapshots": build_seller_snapshots(items, orders, tables["sellers"]),
        "freight": build_freight_table(items, base, products, sellers),
    }
