"""Tests for horizon.py — error by forecast horizon bucket."""

import pandas as pd
import pytest

from app.core.horizon import error_by_horizon, DEFAULT_BUCKETS


def _ts(s: str) -> pd.Timestamp:
    return pd.Timestamp(s, tz="UTC")


def _make_data(forecast_rows, actual_rows):
    """Build forecasts and actuals DataFrames."""
    forecasts = pd.DataFrame(
        forecast_rows, columns=["startTime", "publishTime", "generation"]
    )
    forecasts["startTime"] = pd.to_datetime(forecasts["startTime"], utc=True)
    forecasts["publishTime"] = pd.to_datetime(forecasts["publishTime"], utc=True)

    actuals = pd.DataFrame(actual_rows, columns=["startTime", "generation"])
    actuals["startTime"] = pd.to_datetime(actuals["startTime"], utc=True)
    return forecasts, actuals


class TestErrorByHorizon:
    """Horizon = (startTime - publishTime) in hours, bucketed."""

    def test_basic_buckets(self):
        """Forecasts land in correct buckets and MAE/bias are right."""
        forecasts, actuals = _make_data(
            [
                # horizon = 12 - 7.5 = 4.5h → bucket 0-6
                ("2026-01-10T12:00Z", "2026-01-10T07:30Z", 5000),
                # horizon = 12 - 2 = 10h → bucket 6-12
                ("2026-01-10T12:00Z", "2026-01-10T02:00Z", 5200),
            ],
            [
                ("2026-01-10T12:00Z", 5100),
            ],
        )
        result = error_by_horizon(forecasts, actuals)
        bucket_0_6 = result[result["bucket"] == "0-6"]
        bucket_6_12 = result[result["bucket"] == "6-12"]
        assert len(bucket_0_6) == 1
        assert len(bucket_6_12) == 1
        # 0-6 bucket: error = 5000 - 5100 = -100
        assert bucket_0_6.iloc[0]["mae_mw"] == pytest.approx(100.0)
        assert bucket_0_6.iloc[0]["bias_mw"] == pytest.approx(-100.0)
        # 6-12 bucket: error = 5200 - 5100 = +100
        assert bucket_6_12.iloc[0]["mae_mw"] == pytest.approx(100.0)
        assert bucket_6_12.iloc[0]["bias_mw"] == pytest.approx(100.0)

    def test_exactly_6h_goes_to_6_12(self):
        """Horizon of exactly 6h falls in 6-12 bucket (lower bound inclusive)."""
        forecasts, actuals = _make_data(
            [("2026-01-10T12:00Z", "2026-01-10T06:00Z", 5000)],  # horizon = 6h
            [("2026-01-10T12:00Z", 5100)],
        )
        result = error_by_horizon(forecasts, actuals)
        assert result[result["bucket"] == "6-12"].iloc[0]["count"] == 1
        assert result[result["bucket"] == "0-6"]["count"].sum() == 0

    def test_exactly_12h_goes_to_12_24(self):
        """Horizon of exactly 12h falls in 12-24 bucket."""
        forecasts, actuals = _make_data(
            [("2026-01-10T12:00Z", "2026-01-10T00:00Z", 5000)],  # horizon = 12h
            [("2026-01-10T12:00Z", 5100)],
        )
        result = error_by_horizon(forecasts, actuals)
        assert result[result["bucket"] == "12-24"].iloc[0]["count"] == 1

    def test_48_plus_bucket(self):
        """Horizon > 48h lands in 48+ bucket."""
        forecasts, actuals = _make_data(
            [("2026-01-12T12:00Z", "2026-01-10T00:00Z", 5000)],  # horizon = 60h
            [("2026-01-12T12:00Z", 5100)],
        )
        result = error_by_horizon(forecasts, actuals)
        assert result[result["bucket"] == "48+"].iloc[0]["count"] == 1

    def test_uses_all_forecasts_not_just_selected(self):
        """All forecasts for a slot contribute, not just the latest."""
        forecasts, actuals = _make_data(
            [
                ("2026-01-10T12:00Z", "2026-01-10T07:30Z", 5000),
                ("2026-01-10T12:00Z", "2026-01-10T02:00Z", 5200),
                ("2026-01-10T12:00Z", "2026-01-09T12:00Z", 4800),  # 24h horizon
            ],
            [("2026-01-10T12:00Z", 5100)],
        )
        result = error_by_horizon(forecasts, actuals)
        total = result["count"].sum()
        assert total == 3  # all three forecasts used

    def test_no_matching_actual_excluded(self):
        """Forecasts without a matching actual are silently dropped."""
        forecasts, actuals = _make_data(
            [("2026-01-10T12:00Z", "2026-01-10T07:30Z", 5000)],
            [],  # no actuals
        )
        result = error_by_horizon(forecasts, actuals)
        assert result["count"].sum() == 0

    def test_empty_forecasts(self):
        """Empty input returns all buckets with zero counts."""
        forecasts, actuals = _make_data([], [])
        result = error_by_horizon(forecasts, actuals)
        assert len(result) == len(DEFAULT_BUCKETS)
        assert result["count"].sum() == 0
