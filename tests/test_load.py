"""Tests for the raw data loader. These use small temp files, not the real data."""

import pandas as pd
import pytest

from src.data.load import TABLES, load_table


def test_unknown_table_raises_value_error():
    with pytest.raises(ValueError, match="Unknown table"):
        load_table("not_a_table")


def test_missing_file_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError, match="Missing"):
        load_table("orders", data_dir=tmp_path)


def test_date_columns_are_parsed(tmp_path):
    file_name, date_columns = TABLES["order_items"]
    (tmp_path / file_name).write_text(
        "order_id,shipping_limit_date\nabc,2017-09-19 09:45:35\n", encoding="utf-8"
    )

    df = load_table("order_items", data_dir=tmp_path)

    for column in date_columns:
        assert pd.api.types.is_datetime64_any_dtype(df[column])
