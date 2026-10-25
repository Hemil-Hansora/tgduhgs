"""
Error metrics — quantify forecast accuracy for the buying team.

All metrics are computed on the joined (forecast, actual) pairs.
error = forecast - actual: positive means over-forecast (buyer under-buys,
the risky direction). We never use per-slot MAPE because actual generation
near zero blows it up.
"""

import math

import numpy as np
import pandas as pd


def compute_metrics(joined: pd.DataFrame) -> dict:
    """
    Compute accuracy metrics on a joined forecast/actual DataFrame.

    Expects columns: startTime, forecast, actual.
    Returns a dict with: mae_mw, rmse_mw, bias_mw, p50/p90/p95_abs_error_mw,
    mae_pct_of_mean_actual, buffer_mw, total_slots, dropped_slots.
    """
    total = len(joined)

    if total == 0:
        return _zero_metrics()

    clean = joined.dropna(subset=["forecast", "actual"])
    dropped = total - len(clean)

    if clean.empty:
        m = _zero_metrics()
        m["total_slots"] = total
        m["dropped_slots"] = dropped
        return m

    error = clean["forecast"] - clean["actual"]
    abs_error = error.abs()

    mae = abs_error.mean()
    rmse = math.sqrt((error**2).mean())
    bias = error.mean()
    mean_actual = clean["actual"].mean()

    positive_errors = error[error > 0]
    buffer = (
        float(np.percentile(positive_errors, 90)) if len(positive_errors) > 0 else 0.0
    )

    return {
        "mae_mw": float(mae),
        "rmse_mw": float(rmse),
        "bias_mw": float(bias),
        "p50_abs_error_mw": float(abs_error.quantile(0.50)),
        "p90_abs_error_mw": float(abs_error.quantile(0.90)),
        "p95_abs_error_mw": float(abs_error.quantile(0.95)),
        "mae_pct_of_mean_actual": float(mae / mean_actual * 100)
        if mean_actual != 0
        else 0.0,
        "buffer_mw": buffer,
        "total_slots": total,
        "dropped_slots": dropped,
    }


def _zero_metrics() -> dict:
    return {
        "mae_mw": 0.0,
        "rmse_mw": 0.0,
        "bias_mw": 0.0,
        "p50_abs_error_mw": 0.0,
        "p90_abs_error_mw": 0.0,
        "p95_abs_error_mw": 0.0,
        "mae_pct_of_mean_actual": 0.0,
        "buffer_mw": 0.0,
        "total_slots": 0,
        "dropped_slots": 0,
    }
