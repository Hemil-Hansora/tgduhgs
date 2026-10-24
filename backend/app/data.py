"""
DataProvider: Cache-first data layer with fetch-on-miss and range protection.

Exposes get_actuals(start, end) and get_forecasts(start, end).
Reads committed parquet snapshots from disk at startup into memory.
If a requested range is not covered, fetches via elexon_client up to
MAX_LIVE_FETCH_DAYS, merges into cache, and writes back.
"""

from datetime import date, timedelta
from pathlib import Path
import pandas as pd

from app.config import (
    CACHE_DIR,
    DATA_DIR,
    MAX_LIVE_FETCH_DAYS,
)
from app.elexon_client import fetch_actuals as client_fetch_actuals
from app.elexon_client import fetch_forecasts as client_fetch_forecasts


class RangeExceededError(ValueError):
    """Raised when an uncached range exceeds MAX_LIVE_FETCH_DAYS."""
    pass


class DataProvider:
    """Manages cached wind generation actuals and forecasts."""

    def __init__(
        self,
        data_dir: Path = DATA_DIR,
        cache_dir: Path = CACHE_DIR,
        max_live_days: int = MAX_LIVE_FETCH_DAYS,
    ):
        self.data_dir = Path(data_dir)
        self.cache_dir = Path(cache_dir)
        self.max_live_days = max_live_days

        self.actuals_df = self._load_initial_parquet("actuals.parquet")
        self.forecasts_df = self._load_initial_parquet("forecasts.parquet")

    def _load_initial_parquet(self, filename: str) -> pd.DataFrame:
        """Load from cache_dir if exists, else data_dir, or empty DataFrame."""
        cache_file = self.cache_dir / filename
        data_file = self.data_dir / filename

        for path in (cache_file, data_file):
            if path.exists():
                try:
                    df = pd.read_parquet(path)
                    if "startTime" in df.columns:
                        df["startTime"] = pd.to_datetime(df["startTime"], utc=True)
                    if "publishTime" in df.columns:
                        df["publishTime"] = pd.to_datetime(df["publishTime"], utc=True)
                    return df
                except Exception:
                    continue

        return pd.DataFrame()

    def _save_parquet(self, filename: str, df: pd.DataFrame) -> None:
        """Persist merged DataFrame to cache_dir."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        df.to_parquet(self.cache_dir / filename, index=False)

    # ── Actuals ─────────────────────────────────────────────────────────────

    def get_actuals(self, start: date, end: date) -> pd.DataFrame:
        """
        Get actuals for target range [start, end).

        Checks memory/cache first. If range is not covered, fetches from
        Elexon (capped at max_live_days), merges, and caches.
        """
        if start >= end:
            raise ValueError(f"Start date ({start}) must be before end date ({end}).")

        start_ts = pd.Timestamp(start, tz="UTC")
        end_ts = pd.Timestamp(end, tz="UTC")

        # Check coverage in current DataFrame
        if not self._is_actuals_covered(start_ts, end_ts):
            span_days = (end - start).days
            if span_days > self.max_live_days:
                raise RangeExceededError(
                    f"Requested live fetch range ({span_days} days) exceeds limit of "
                    f"{self.max_live_days} days. Please use scripts/ingest.py to prebuild data."
                )

            # Fetch, merge, and persist
            fetched = client_fetch_actuals(start, end)
            if not fetched.empty:
                self.actuals_df = self._merge_actuals(fetched)
                self._save_parquet("actuals.parquet", self.actuals_df)

        if self.actuals_df.empty:
            return pd.DataFrame(columns=["startTime", "generation"])

        mask = (self.actuals_df["startTime"] >= start_ts) & (self.actuals_df["startTime"] < end_ts)
        return self.actuals_df[mask].copy().reset_index(drop=True)

    def _is_actuals_covered(self, start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> bool:
        """Return True if actuals_df contains the full range [start_ts, end_ts)."""
        if self.actuals_df.empty or "startTime" not in self.actuals_df.columns:
            return False
        min_ts = self.actuals_df["startTime"].min()
        max_ts = self.actuals_df["startTime"].max()
        # Half-hour slots: max slot is at least end_ts - 30 minutes
        return min_ts <= start_ts and max_ts >= (end_ts - pd.Timedelta(minutes=30))

    def _merge_actuals(self, new_df: pd.DataFrame) -> pd.DataFrame:
        """Merge new actuals with existing and deduplicate."""
        if self.actuals_df.empty:
            return new_df.copy().reset_index(drop=True)
        merged = pd.concat([self.actuals_df, new_df], ignore_index=True)
        return (
            merged.drop_duplicates(subset=["startTime"])
            .sort_values("startTime")
            .reset_index(drop=True)
        )

    # ── Forecasts ───────────────────────────────────────────────────────────

    def get_forecasts(self, start: date, end: date) -> pd.DataFrame:
        """
        Get forecasts targeting delivery slots in [start, end).

        Checks memory/cache first. If target slots are not covered, fetches
        historical forecasts published before and during the target window,
        merges, and caches.
        """
        if start >= end:
            raise ValueError(f"Start date ({start}) must be before end date ({end}).")

        start_ts = pd.Timestamp(start, tz="UTC")
        end_ts = pd.Timestamp(end, tz="UTC")

        if not self._is_forecasts_covered(start_ts, end_ts):
            span_days = (end - start).days
            if span_days > self.max_live_days:
                raise RangeExceededError(
                    f"Requested live fetch range ({span_days} days) exceeds limit of "
                    f"{self.max_live_days} days. Please use scripts/ingest.py to prebuild data."
                )

            # Fetch forecasts published starting 4 days earlier to cover the start of the window
            pub_start = start - timedelta(days=4)
            fetched_raw = client_fetch_forecasts(pub_start, end)
            if not fetched_raw.empty:
                # Keep target slots within the requested window
                fetched = fetched_raw[
                    (fetched_raw["startTime"] >= start_ts) & (fetched_raw["startTime"] < end_ts)
                ].copy()
                self.forecasts_df = self._merge_forecasts(fetched)
                self._save_parquet("forecasts.parquet", self.forecasts_df)

        if self.forecasts_df.empty:
            return pd.DataFrame(columns=["startTime", "publishTime", "generation"])

        mask = (self.forecasts_df["startTime"] >= start_ts) & (self.forecasts_df["startTime"] < end_ts)
        return self.forecasts_df[mask].copy().reset_index(drop=True)

    def _is_forecasts_covered(self, start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> bool:
        """Return True if forecasts_df covers the target delivery range."""
        if self.forecasts_df.empty or "startTime" not in self.forecasts_df.columns:
            return False
        min_ts = self.forecasts_df["startTime"].min()
        max_ts = self.forecasts_df["startTime"].max()
        # Hourly slots: max slot is at least end_ts - 1 hour
        return min_ts <= start_ts and max_ts >= (end_ts - pd.Timedelta(hours=1))

    def _merge_forecasts(self, new_df: pd.DataFrame) -> pd.DataFrame:
        """Merge new forecasts with existing and deduplicate."""
        if self.forecasts_df.empty:
            return new_df.copy().reset_index(drop=True)
        merged = pd.concat([self.forecasts_df, new_df], ignore_index=True)
        return (
            merged.drop_duplicates(subset=["startTime", "publishTime"])
            .sort_values(["startTime", "publishTime"])
            .reset_index(drop=True)
        )
