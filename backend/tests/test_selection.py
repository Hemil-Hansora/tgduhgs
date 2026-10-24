"""Tests for selection.py — forecast cutoff logic."""

import pandas as pd
import pytest

from app.core.selection import select_forecasts, align_actuals_to_hourly


def _ts(s: str) -> pd.Timestamp:
    """Shorthand for UTC timestamp."""
    return pd.Timestamp(s, tz="UTC")


def _forecasts_df(rows: list[tuple]) -> pd.DataFrame:
    """Build a forecasts DataFrame from (startTime, publishTime, generation) tuples."""
    df = pd.DataFrame(rows, columns=["startTime", "publishTime", "generation"])
    df["startTime"] = pd.to_datetime(df["startTime"], utc=True)
    df["publishTime"] = pd.to_datetime(df["publishTime"], utc=True)
    return df


# ── Cutoff filtering ────────────────────────────────────────────────────────

class TestSelectForecasts:
    """Core cutoff rule: for target day D, cutoff = D-1 09:00 UTC."""

    def test_after_cutoff_never_chosen(self):
        """A forecast published AFTER the cutoff must be excluded."""
        df = _forecasts_df([
            # Target: 2026-01-10 12:00. Cutoff: 2026-01-09 09:00.
            ("2026-01-10T12:00:00Z", "2026-01-09T10:00:00Z", 5000),  # after cutoff
        ])
        result = select_forecasts(df, cutoff_hour_utc=9)
        assert len(result) == 0

    def test_exactly_at_cutoff_is_included(self):
        """A forecast published exactly at cutoff (<=) must be included."""
        df = _forecasts_df([
            # Target: 2026-01-10 12:00. Cutoff: 2026-01-09 09:00.
            ("2026-01-10T12:00:00Z", "2026-01-09T09:00:00Z", 5000),  # exactly at cutoff
        ])
        result = select_forecasts(df, cutoff_hour_utc=9)
        assert len(result) == 1
        assert result.iloc[0]["generation"] == 5000

    def test_latest_valid_wins(self):
        """Among multiple valid forecasts, the one with max publishTime wins."""
        df = _forecasts_df([
            ("2026-01-10T12:00:00Z", "2026-01-09T02:30:00Z", 4000),  # early
            ("2026-01-10T12:00:00Z", "2026-01-09T07:30:00Z", 5500),  # latest valid
            ("2026-01-10T12:00:00Z", "2026-01-09T04:30:00Z", 4500),  # middle
            ("2026-01-10T12:00:00Z", "2026-01-09T10:00:00Z", 6000),  # after cutoff
        ])
        result = select_forecasts(df, cutoff_hour_utc=9)
        assert len(result) == 1
        assert result.iloc[0]["generation"] == 5500
        assert result.iloc[0]["publishTime"] == _ts("2026-01-09T07:30:00Z")

    def test_multiple_target_slots(self):
        """Each target slot gets its own selected forecast independently."""
        df = _forecasts_df([
            ("2026-01-10T12:00:00Z", "2026-01-09T07:30:00Z", 5500),
            ("2026-01-10T13:00:00Z", "2026-01-09T04:30:00Z", 3000),
            ("2026-01-10T13:00:00Z", "2026-01-09T07:30:00Z", 3200),
        ])
        result = select_forecasts(df, cutoff_hour_utc=9)
        assert len(result) == 2
        # Check each slot got the right one
        row_12 = result[result["startTime"] == _ts("2026-01-10T12:00:00Z")].iloc[0]
        row_13 = result[result["startTime"] == _ts("2026-01-10T13:00:00Z")].iloc[0]
        assert row_12["generation"] == 5500
        assert row_13["generation"] == 3200

    def test_cutoff_column_present(self):
        """Result must include a 'cutoff' column showing the cutoff used."""
        df = _forecasts_df([
            ("2026-01-10T12:00:00Z", "2026-01-09T07:30:00Z", 5500),
        ])
        result = select_forecasts(df, cutoff_hour_utc=9)
        assert "cutoff" in result.columns
        assert result.iloc[0]["cutoff"] == _ts("2026-01-09T09:00:00Z")

    def test_custom_cutoff_hour(self):
        """Cutoff hour is configurable."""
        df = _forecasts_df([
            # Target: 2026-01-10 12:00. Cutoff at hour=6: 2026-01-09 06:00.
            ("2026-01-10T12:00:00Z", "2026-01-09T05:00:00Z", 4000),  # valid
            ("2026-01-10T12:00:00Z", "2026-01-09T07:00:00Z", 5000),  # after cutoff=6
        ])
        result = select_forecasts(df, cutoff_hour_utc=6)
        assert len(result) == 1
        assert result.iloc[0]["generation"] == 4000

    def test_empty_input(self):
        """Empty DataFrame returns empty DataFrame with correct columns."""
        df = _forecasts_df([])
        result = select_forecasts(df, cutoff_hour_utc=9)
        assert len(result) == 0
        assert "startTime" in result.columns


# ── Alignment ────────────────────────────────────────────────────────────────

class TestAlignActuals:
    """FUELHH is 30-min, WINDFOR is hourly → resample actuals to hourly mean."""

    def test_pairs_averaged(self):
        """Two half-hour slots become one hourly slot with mean generation."""
        df = pd.DataFrame({
            "startTime": pd.to_datetime([
                "2026-01-10T12:00:00Z", "2026-01-10T12:30:00Z",
                "2026-01-10T13:00:00Z", "2026-01-10T13:30:00Z",
            ], utc=True),
            "generation": [4000, 6000, 3000, 5000],
        })
        result = align_actuals_to_hourly(df)
        assert len(result) == 2
        assert result.iloc[0]["generation"] == 5000.0   # mean(4000, 6000)
        assert result.iloc[1]["generation"] == 4000.0   # mean(3000, 5000)
        # startTime should be the hour mark
        assert result.iloc[0]["startTime"] == _ts("2026-01-10T12:00:00Z")

    def test_single_slot_kept(self):
        """If only one half-hour exists for an hour, it passes through."""
        df = pd.DataFrame({
            "startTime": pd.to_datetime(["2026-01-10T12:00:00Z"], utc=True),
            "generation": [4000],
        })
        result = align_actuals_to_hourly(df)
        assert len(result) == 1
        assert result.iloc[0]["generation"] == 4000.0
