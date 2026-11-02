"""Shared feature helpers, including history that respects time."""

import holidays
import numpy as np
import pandas as pd

# How many past observations it takes for a group's own rate to outweigh the
# overall rate. This stops a seller with one late order from scoring 100%.
PRIOR_WEIGHT = 20

PEAK_WINDOW_DAYS = 5


def haversine_km(lat1, lng1, lat2, lng2):
    """Return the great-circle distance in kilometres."""
    lat1, lng1, lat2, lng2 = map(np.radians, (lat1, lng1, lat2, lng2))
    a = (
        np.sin((lat2 - lat1) / 2) ** 2
        + np.cos(lat1) * np.cos(lat2) * np.sin((lng2 - lng1) / 2) ** 2
    )
    return 6371 * 2 * np.arcsin(np.sqrt(a))


def days_between(start, end):
    """Return the number of days from start to end as a float."""
    return (end - start).dt.total_seconds() / 86400


def past_totals(times, history_known_at, history_values, keys=None, history_keys=None):
    """Return the count and sum of history values known strictly before each time.

    A value counts from the moment it became known, so a row can never see an
    outcome from its own future. With keys, only matching groups are counted.
    """
    if keys is None:
        keys = pd.Series("all", index=times.index)
        history_keys = pd.Series("all", index=history_known_at.index)

    past = pd.DataFrame(
        {
            "known_at": history_known_at.astype("datetime64[us]"),
            "key": history_keys,
            "value": history_values.astype(float),
        }
    ).dropna(subset=["known_at", "value"])
    past = past.sort_values("known_at")
    past["count"] = past.groupby("key").cumcount() + 1.0
    past["total"] = past.groupby("key")["value"].cumsum()

    query = pd.DataFrame(
        {"time": times.astype("datetime64[us]"), "key": keys, "row": times.index}
    ).sort_values("time")
    merged = pd.merge_asof(
        query,
        past,
        left_on="time",
        right_on="known_at",
        by="key",
        allow_exact_matches=False,
    )
    result = merged.set_index("row")[["count", "total"]].fillna(0.0)
    return result.reindex(times.index)


def window_totals(times, days, history_known_at, history_values, keys=None, history_keys=None):
    """Return the count and sum of values that became known in the days before each time."""
    args = (history_known_at, history_values, keys, history_keys)
    return past_totals(times, *args) - past_totals(times - pd.Timedelta(days=days), *args)


def safe_rate(totals):
    """Return total divided by count, or missing where there's no history."""
    return totals["total"] / totals["count"].where(totals["count"] > 0)


def smoothed_rate(totals, prior):
    """Blend a group's own rate with the overall rate, weighted by its history."""
    return (totals["total"] + PRIOR_WEIGHT * prior) / (totals["count"] + PRIOR_WEIGHT)


def brazil_holidays(years):
    """Return the set of Brazilian national holidays as timestamps."""
    return {pd.Timestamp(day) for day in holidays.country_holidays("BR", years=years)}


def black_friday(year):
    """Return the Friday after the fourth Thursday of November."""
    thursdays = pd.date_range(f"{year}-11-01", f"{year}-11-30", freq="W-THU")
    return thursdays[3] + pd.Timedelta(days=1)


def peak_window_days(years):
    """Return the days of the Black Friday surge, which lasted five days in 2017."""
    return {
        black_friday(year) + pd.Timedelta(days=offset)
        for year in years
        for offset in range(PEAK_WINDOW_DAYS)
    }
