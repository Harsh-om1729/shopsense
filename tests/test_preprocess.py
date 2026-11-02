"""Tests for preprocessing rules, using small made-up tables."""

import pandas as pd
import pytest

from src import config
from src.data.make_dataset import validate
from src.data.preprocess import (
    POST_PURCHASE_COLUMNS,
    assign_period,
    build_daily_orders,
    build_delivery_table,
    build_freight_table,
    build_review_table,
    build_seller_snapshots,
    build_weekly_category,
    clean_orders,
    clean_products,
    clean_zip_coordinates,
    latest_reviews,
    summarise_items,
    summarise_payments,
)


def base_orders(**overrides):
    """Return one delivered order, with any columns replaced."""
    row = {
        "order_id": "a",
        "customer_id": "c",
        "order_status": "delivered",
        "order_purchase_timestamp": pd.Timestamp("2018-01-01 10:00"),
        "order_approved_at": pd.Timestamp("2018-01-01 11:00"),
        "order_delivered_carrier_date": pd.Timestamp("2018-01-02"),
        "order_delivered_customer_date": pd.Timestamp("2018-01-06 12:00"),
        "order_estimated_delivery_date": pd.Timestamp("2018-01-05"),
    }
    return pd.DataFrame([{**row, **overrides}])


def base_table(**overrides):
    """Return an order base row with the purchase-time columns filled in."""
    extra = dict.fromkeys(
        [
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
        ],
        1,
    )
    return base_orders(**{**extra, **overrides})


def test_assign_period_labels_each_side_of_the_holdout():
    dates = pd.Series(pd.to_datetime(["2018-01-01", "2018-05-15", "2018-06-01"]))
    assert assign_period(dates).tolist() == ["development", "embargo", "holdout"]


def test_assign_period_embargoes_rows_with_a_late_outcome():
    event = pd.Series(pd.to_datetime(["2018-04-01"]))
    outcome = pd.Series(pd.to_datetime(["2018-06-10"]))
    assert assign_period(event, outcome).tolist() == ["embargo"]


def test_clean_orders_drops_dates_outside_the_range():
    orders = pd.concat(
        [
            base_orders(order_id="old", order_purchase_timestamp=pd.Timestamp("2016-10-01")),
            base_orders(order_id="keep"),
            base_orders(
                order_id="last",
                order_purchase_timestamp=pd.Timestamp(f"{config.LAST_ORDER_DATE} 23:00"),
            ),
            base_orders(order_id="after", order_purchase_timestamp=pd.Timestamp("2018-08-22")),
        ]
    )
    assert clean_orders(orders)["order_id"].tolist() == ["keep", "last"]


def test_clean_orders_clears_impossible_carrier_dates():
    orders = base_orders(order_delivered_carrier_date=pd.Timestamp("2017-12-01"))
    assert clean_orders(orders)["order_delivered_carrier_date"].isna().all()


def test_clean_zip_coordinates_ignores_points_outside_brazil():
    geolocation = pd.DataFrame(
        {
            "geolocation_zip_code_prefix": [1, 1, 1],
            "geolocation_lat": [-23.0, -23.0, 40.0],
            "geolocation_lng": [-46.0, -46.0, -3.0],
        }
    )
    coords = clean_zip_coordinates(geolocation)
    assert coords.loc[1, "lat"] == -23.0


def test_clean_products_handles_missing_translations_and_zero_weight():
    products = pd.DataFrame(
        {
            "product_id": ["a", "b", "c"],
            "product_category_name": ["cama", "pc_gamer", None],
            "product_name_lenght": [1.0, 2.0, 3.0],
            "product_description_lenght": [1.0, 2.0, 3.0],
            "product_weight_g": [100.0, 0.0, 50.0],
        }
    )
    translation = pd.DataFrame(
        {"product_category_name": ["cama"], "product_category_name_english": ["bed"]}
    )

    cleaned = clean_products(products, translation)

    assert cleaned["category"].tolist() == ["bed", "pc_gamer", "unknown"]
    assert pd.isna(cleaned.loc[1, "product_weight_g"])
    assert "product_name_length" in cleaned.columns


def test_summarise_payments_gives_one_row_and_fixes_zero_installments():
    payments = pd.DataFrame(
        {
            "order_id": ["a", "a"],
            "payment_sequential": [1, 2],
            "payment_type": ["voucher", "credit_card"],
            "payment_installments": [0, 0],
            "payment_value": [10.0, 90.0],
        }
    )
    summary = summarise_payments(payments)

    assert len(summary) == 1
    assert summary.loc["a", "payment_value_total"] == 100.0
    assert summary.loc["a", "payment_installments"] == 1
    assert summary.loc["a", "payment_type"] == "credit_card"


def test_summarise_items_counts_the_order_once_and_picks_the_priciest_item():
    items = pd.DataFrame(
        {
            "order_id": ["a", "a"],
            "order_item_id": [1, 2],
            "product_id": ["p1", "p2"],
            "seller_id": ["s1", "s2"],
            "price": [10.0, 30.0],
            "freight_value": [1.0, 2.0],
        }
    )
    products = pd.DataFrame(
        {"product_id": ["p1", "p2"], "category": ["x", "y"], "product_weight_g": [100.0, 200.0]}
    )
    summary = summarise_items(items, products)

    assert len(summary) == 1
    assert summary.loc["a", "n_sellers"] == 2
    assert summary.loc["a", "item_total"] == 40.0
    assert summary.loc["a", "total_weight_g"] == 300.0
    assert summary.loc["a", "seller_id"] == "s2"


def test_latest_reviews_keeps_the_most_recent_answer():
    reviews = pd.DataFrame(
        {
            "order_id": ["a", "a"],
            "review_score": [1, 5],
            "review_answer_timestamp": pd.to_datetime(["2018-01-02", "2018-01-01"]),
        }
    )
    assert latest_reviews(reviews)["review_score"].tolist() == [1]


def test_delivery_table_builds_targets_without_post_purchase_columns():
    table = build_delivery_table(base_table())

    assert table["is_late"].tolist() == [True]
    assert table["days_to_deliver"].iloc[0] == pytest.approx(5.083, abs=0.01)
    assert not set(table.columns) & set(POST_PURCHASE_COLUMNS)


def test_delivery_table_is_not_late_on_the_promised_day():
    table = build_delivery_table(
        base_table(order_delivered_customer_date=pd.Timestamp("2018-01-05 23:00"))
    )
    assert table["is_late"].tolist() == [False]


def test_delivery_table_skips_orders_that_were_not_delivered():
    assert build_delivery_table(base_table(order_status="canceled")).empty


def test_daily_orders_fills_days_without_orders():
    orders = pd.DataFrame(
        {"order_purchase_timestamp": pd.to_datetime(["2018-08-18 10:00", "2018-08-20 10:00"])}
    )
    daily = build_daily_orders(orders)

    assert daily["orders"].tolist() == [1, 0, 1, 0]
    assert daily["date"].iloc[-1] == pd.Timestamp(config.LAST_ORDER_DATE)


def test_weekly_category_uses_complete_weeks_only():
    items = pd.DataFrame({"order_id": ["a", "b"], "product_id": ["p", "p"]})
    orders = pd.DataFrame(
        {
            "order_id": ["a", "b"],
            # A Wednesday, so the first week is incomplete and left out.
            "order_purchase_timestamp": pd.to_datetime(["2018-05-02", "2018-05-08"]),
        }
    )
    products = pd.DataFrame({"product_id": ["p"], "category": ["x"]})

    table = build_weekly_category(items, orders, products)

    assert table["week_end"].min() == pd.Timestamp("2018-05-13")
    assert table.loc[table["week_end"] == "2018-05-13", "items"].tolist() == [1]


def test_seller_snapshots_ignore_cancelled_sales_and_mark_inactive_sellers():
    items = pd.DataFrame(
        {"order_id": ["old1", "old2", "new1", "new2"], "seller_id": ["s1", "s2", "s1", "s2"]}
    )
    orders = pd.DataFrame(
        {
            "order_id": ["old1", "old2", "new1", "new2"],
            "order_status": ["delivered", "delivered", "delivered", "canceled"],
            "order_purchase_timestamp": pd.to_datetime(
                ["2018-03-15", "2018-03-15", "2018-04-10", "2018-04-10"]
            ),
        }
    )
    sellers = pd.DataFrame({"seller_id": ["s1", "s2"], "seller_state": ["SP", "RJ"]})

    table = build_seller_snapshots(items, orders, sellers)
    april = table[table["snapshot_date"] == "2018-04-01"].set_index("seller_id")

    assert not april.loc["s1", "is_inactive"]
    assert april.loc["s2", "is_inactive"]


def test_freight_table_turns_repeats_into_a_quantity():
    items = pd.DataFrame(
        {
            "order_id": ["a", "a"],
            "order_item_id": [1, 2],
            "product_id": ["p", "p"],
            "seller_id": ["s", "s"],
            "price": [10.0, 10.0],
            "freight_value": [3.0, 3.0],
        }
    )
    base = pd.DataFrame(
        {
            "order_id": ["a"],
            "order_purchase_timestamp": pd.to_datetime(["2018-01-01"]),
            "customer_state": ["SP"],
            "customer_lat": [-23.0],
            "customer_lng": [-46.0],
        }
    )
    sellers = pd.DataFrame(
        {"seller_id": ["s"], "seller_state": ["RJ"], "seller_lat": [-22.0], "seller_lng": [-43.0]}
    )
    products = pd.DataFrame(
        {
            "product_id": ["p"],
            "category": ["x"],
            "product_weight_g": [100.0],
            "product_length_cm": [1.0],
            "product_height_cm": [1.0],
            "product_width_cm": [1.0],
        }
    )

    table = build_freight_table(items, base, products, sellers)

    assert len(table) == 1
    assert table.loc[0, "quantity"] == 2
    assert table.loc[0, "freight_value"] == 3.0
    assert table.loc[0, "seller_state"] == "RJ"


def review_row(score, created, order_id="a"):
    """Return one review for an order."""
    return {
        "order_id": order_id,
        "review_score": score,
        "review_creation_date": pd.Timestamp(created),
        "review_answer_timestamp": pd.Timestamp(created) + pd.Timedelta(days=1),
    }


def test_review_table_keeps_overdue_orders_and_hides_their_delivery_date():
    # Promised 5 January, delivered 6 January, reviewed before it arrived.
    base = base_table(order_delivered_customer_date=pd.Timestamp("2018-01-10 12:00"))
    reviews = pd.DataFrame([review_row(1, "2018-01-07")])

    table = build_review_table(base, reviews)

    assert len(table) == 1
    assert table["is_overdue"].tolist() == [True]
    assert table["is_low"].tolist() == [True]
    assert table["delivered_date"].isna().all()
    assert table["prediction_moment"].iloc[0] == pd.Timestamp("2018-01-06")


def test_review_table_shows_the_delivery_date_of_on_time_orders():
    base = base_table(order_delivered_customer_date=pd.Timestamp("2018-01-04 12:00"))
    reviews = pd.DataFrame([review_row(5, "2018-01-05")])

    table = build_review_table(base, reviews)

    assert table["is_overdue"].tolist() == [False]
    assert table["delivered_date"].iloc[0] == pd.Timestamp("2018-01-04 12:00")


def test_review_table_drops_reviews_written_before_the_moment():
    base = base_table(order_delivered_customer_date=pd.Timestamp("2018-01-04 12:00"))
    reviews = pd.DataFrame([review_row(5, "2018-01-02")])

    assert build_review_table(base, reviews).empty


def test_validate_rejects_duplicate_keys():
    table = pd.DataFrame({"order_id": ["a", "a"], "period": ["development"] * 2})
    with pytest.raises(ValueError, match="duplicate"):
        validate({"delivery": table})
