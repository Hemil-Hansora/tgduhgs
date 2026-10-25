"""Tests for metrics.py — error metrics on joined forecast/actual data."""

import math

import pandas as pd
import pytest
from app.core.metrics import compute_metrics


def _ts(s: str) -> pd.Timestamp:
    return pd.Timestamp(s, tz="UTC")


def _joined_df(rows: list[tuple]) -> pd.DataFrame:
    """Build joined DataFrame from (startTime, forecast, actual) tuples."""
    df = pd.DataFrame(rows, columns=["startTime", "forecast", "actual"])
    df["startTime"] = pd.to_datetime(df["startTime"], utc=True)
    return df


class TestComputeMetrics:
    """Hand-computed metrics on a 4-row example.

    Rows:
        forecast  actual  error   abs_error
        100       80      +20     20
        90        100     -10     10
        110       110      0       0
        80        60      +20     20

    bias  = mean(20, -10, 0, 20)        = 7.5
    MAE   = mean(20, 10, 0, 20)         = 12.5
    RMSE  = sqrt(mean(400,100,0,400))   = sqrt(225) = 15.0
    P50 abs = median(0,10,20,20)        = 15.0
    P90 abs = 90th percentile           = 20.0
    P95 abs = 95th percentile           = 20.0
    mean actual = mean(80,100,110,60)   = 87.5
    MAE % of mean actual = 12.5/87.5    ≈ 14.2857%
    positive errors = [20, 20], P90      = 20.0
    """

    @pytest.fixture
    def df(self):
        return _joined_df(
            [
                ("2026-01-10T00:00Z", 100, 80),
                ("2026-01-10T01:00Z", 90, 100),
                ("2026-01-10T02:00Z", 110, 110),
                ("2026-01-10T03:00Z", 80, 60),
            ]
        )

    def test_bias(self, df):
        m = compute_metrics(df)
        assert m["bias_mw"] == pytest.approx(7.5)

    def test_mae(self, df):
        m = compute_metrics(df)
        assert m["mae_mw"] == pytest.approx(12.5)

    def test_rmse(self, df):
        m = compute_metrics(df)
        assert m["rmse_mw"] == pytest.approx(15.0)

    def test_percentiles(self, df):
        m = compute_metrics(df)
        assert m["p50_abs_error_mw"] == pytest.approx(15.0)
        assert m["p90_abs_error_mw"] == pytest.approx(20.0)
        assert m["p95_abs_error_mw"] == pytest.approx(20.0)

    def test_mae_pct(self, df):
        m = compute_metrics(df)
        assert m["mae_pct_of_mean_actual"] == pytest.approx(12.5 / 87.5 * 100)

    def test_buffer(self, df):
        """Buffer = P90 of positive errors (over-forecasts)."""
        m = compute_metrics(df)
        # Positive errors: [20, 20] → P90 = 20
        assert m["buffer_mw"] == pytest.approx(20.0)

    def test_slot_count(self, df):
        m = compute_metrics(df)
        assert m["total_slots"] == 4
        assert m["dropped_slots"] == 0

    def test_with_nan_drops_and_counts(self):
        """Rows with NaN actual or forecast are dropped and counted."""
        df = _joined_df(
            [
                ("2026-01-10T00:00Z", 100, 80),
                ("2026-01-10T01:00Z", 90, float("nan")),
                ("2026-01-10T02:00Z", float("nan"), 110),
            ]
        )
        m = compute_metrics(df)
        assert m["total_slots"] == 3
        assert m["dropped_slots"] == 2
        # Only one valid row: error=20, so MAE=20
        assert m["mae_mw"] == pytest.approx(20.0)

    def test_no_positive_errors_buffer_is_zero(self):
        """If all errors are negative or zero, buffer should be 0."""
        df = _joined_df(
            [
                ("2026-01-10T00:00Z", 80, 100),  # -20
                ("2026-01-10T01:00Z", 100, 100),  # 0
            ]
        )
        m = compute_metrics(df)
        assert m["buffer_mw"] == pytest.approx(0.0)

    def test_empty_input(self):
        """Empty input returns zeroed metrics."""
        df = _joined_df([])
        m = compute_metrics(df)
        assert m["total_slots"] == 0
        assert m["mae_mw"] == 0.0
