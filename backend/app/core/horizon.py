"""
Forecast error by horizon — how does accuracy degrade with lead time?

Horizon = (startTime - publishTime) in hours. We bucket every forecast
(not just the selected one) and report MAE and bias per bucket. This shows
the buyer whether short-range forecasts are meaningfully better.
"""

import pandas as pd
import numpy as np

# (lower_bound_inclusive, upper_bound_exclusive, label)
DEFAULT_BUCKETS: list[tuple[float, float, str]] = [
    (0, 6, "0-6"),
    (6, 12, "6-12"),
    (12, 24, "12-24"),
    (24, 48, "24-48"),
    (48, float("inf"), "48+"),
]


def error_by_horizon(
    forecasts: pd.DataFrame,
    actuals: pd.DataFrame,
    buckets: list[tuple[float, float, str]] | None = None,
) -> pd.DataFrame:
    """
    Compute MAE and bias per horizon bucket using ALL forecasts.

    Joins every forecast row to its matching actual on startTime,
    computes horizon_h = (startTime - publishTime) in hours,
    assigns each to a bucket, and aggregates.

    Returns DataFrame with columns: bucket, mae_mw, bias_mw, count.
    """
    if buckets is None:
        buckets = DEFAULT_BUCKETS

    # Start with empty result for all buckets
    empty = pd.DataFrame(
        [(label, 0.0, 0.0, 0) for _, _, label in buckets],
        columns=["bucket", "mae_mw", "bias_mw", "count"],
    )

    if forecasts.empty or actuals.empty:
        return empty

    # Join forecasts to actuals on startTime
    merged = forecasts.merge(
        actuals[["startTime", "generation"]],
        on="startTime",
        suffixes=("_forecast", "_actual"),
    )

    if merged.empty:
        return empty

    merged["error"] = merged["generation_forecast"] - merged["generation_actual"]
    merged["horizon_h"] = (
        merged["startTime"] - merged["publishTime"]
    ).dt.total_seconds() / 3600

    # Assign buckets
    merged["bucket"] = _assign_bucket(merged["horizon_h"], buckets)

    # Aggregate per bucket
    agg = merged.groupby("bucket", as_index=False).agg(
        mae_mw=("error", lambda x: x.abs().mean()),
        bias_mw=("error", "mean"),
        count=("error", "size"),
    )

    # Merge with empty to ensure all buckets present, fill missing with zeros
    result = empty[["bucket"]].merge(agg, on="bucket", how="left").fillna(0)
    result["count"] = result["count"].astype(int)
    return result.reset_index(drop=True)


def _assign_bucket(
    horizon_h: pd.Series, buckets: list[tuple[float, float, str]]
) -> pd.Series:
    """Map horizon hours to bucket labels. Lower bound inclusive, upper exclusive."""
    labels = pd.Series("", index=horizon_h.index)
    for low, high, label in buckets:
        mask = (horizon_h >= low) & (horizon_h < high)
        labels[mask] = label
    return labels
