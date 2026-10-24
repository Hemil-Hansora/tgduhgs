#!/usr/bin/env python3
"""
Ingest Elexon BMRS data into parquet files.

Usage:
    python scripts/ingest.py --start 2026-01-02 --end 2026-02-02

Fetches FUELHH wind actuals and WINDFOR forecasts, saves to data/*.parquet.
If files already exist, merges new data and drops duplicates.
"""

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

# Add backend to path so we can import the shared client
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import pandas as pd
from app.elexon_client import fetch_actuals, fetch_forecasts

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _merge_parquet(path: Path, new_df: pd.DataFrame, dedup_cols: list[str]) -> pd.DataFrame:
    """Load existing parquet (if any), append new_df, deduplicate, save."""
    if path.exists():
        old = pd.read_parquet(path)
        df = pd.concat([old, new_df], ignore_index=True)
    else:
        df = new_df
    df = df.drop_duplicates(subset=dedup_cols).sort_values(dedup_cols).reset_index(drop=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return df


def _report_actuals(df: pd.DataFrame, start: date, end: date) -> None:
    """Print summary and find missing 30-min slots."""
    print(f"\n── Actuals ──")
    print(f"  Rows:      {len(df)}")
    if df.empty:
        print("  (no data)")
        return
    print(f"  startTime: {df['startTime'].min()} → {df['startTime'].max()}")

    # Expected 30-min slots from start 00:00 to end 00:00 (exclusive)
    expected = pd.date_range(
        pd.Timestamp(start, tz="UTC"),
        pd.Timestamp(end, tz="UTC") - pd.Timedelta(minutes=30),
        freq="30min",
    )
    actual_times = set(df["startTime"])
    missing = sorted(set(expected) - actual_times)
    print(f"  Expected slots: {len(expected)}")
    print(f"  Missing slots:  {len(missing)}")
    if missing:
        for t in missing[:20]:
            print(f"    {t}")
        if len(missing) > 20:
            print(f"    ... and {len(missing) - 20} more")


def _report_forecasts(df: pd.DataFrame) -> None:
    """Print summary."""
    print(f"\n── Forecasts ──")
    print(f"  Rows:        {len(df)}")
    if df.empty:
        print("  (no data)")
        return
    print(f"  startTime:   {df['startTime'].min()} → {df['startTime'].max()}")
    print(f"  publishTime: {df['publishTime'].min()} → {df['publishTime'].max()}")
    unique_targets = df["startTime"].nunique()
    print(f"  Unique target slots: {unique_targets}")
    print(f"  Avg forecasts/slot:  {len(df) / unique_targets:.1f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Elexon wind data")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD (inclusive)")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD (exclusive)")
    args = parser.parse_args()

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)

    # ── Actuals ──────────────────────────────────────────────────────────
    print(f"Fetching actuals {start} → {end} ...")
    actuals = fetch_actuals(start, end)
    actuals = _merge_parquet(DATA_DIR / "actuals.parquet", actuals, ["startTime"])
    _report_actuals(actuals, start, end)

    # ── Forecasts ────────────────────────────────────────────────────────
    # We need forecasts whose *target* startTime is in [start, end).
    # But we filter by publishTime, so we fetch from a few days before start
    # to capture early forecasts targeting the start of our window.
    # Forecasts cover ~73h ahead, so publishing 4 days before start should suffice.
    pub_start = start - timedelta(days=4)
    pub_end = end
    print(f"\nFetching forecasts (publishTime {pub_start} → {pub_end}) ...")
    forecasts_raw = fetch_forecasts(pub_start, pub_end)

    # Keep only rows whose target startTime falls in our window
    window_start = pd.Timestamp(start, tz="UTC")
    window_end = pd.Timestamp(end, tz="UTC")
    forecasts = forecasts_raw[
        (forecasts_raw["startTime"] >= window_start) &
        (forecasts_raw["startTime"] < window_end)
    ].copy()
    print(f"  Filtered to target window: {len(forecasts)} rows (from {len(forecasts_raw)} raw)")

    forecasts = _merge_parquet(
        DATA_DIR / "forecasts.parquet", forecasts, ["startTime", "publishTime"]
    )
    _report_forecasts(forecasts)

    print("\nDone.")


if __name__ == "__main__":
    main()
