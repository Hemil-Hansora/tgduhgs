"""
Elexon BMRS API client — fetches FUELHH (wind actuals) and WINDFOR (forecasts).

All returned DataFrames have tz-aware UTC datetime columns.
Handles chunking (API has no hard limit, but we chunk by day to be safe),
retries with backoff on 429/5xx, and request timeouts.
"""

import time
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import requests

BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1"
REQUEST_TIMEOUT = 60  # seconds per request
MAX_RETRIES = 5
INITIAL_BACKOFF = 2  # seconds, doubles each retry
# Chunk sizes for splitting large date ranges
ACTUALS_CHUNK_DAYS = 7
FORECASTS_CHUNK_DAYS = 1  # WINDFOR by publishTime; 1 day keeps responses small


def _get_json(url: str, params: dict) -> list[dict]:
    """GET with retry + backoff on 429 / 5xx. Returns parsed JSON list."""
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        except requests.exceptions.RequestException as exc:
            if attempt == MAX_RETRIES - 1:
                raise
            _backoff(attempt, reason=str(exc))
            continue

        if resp.status_code == 200:
            return resp.json()

        if resp.status_code in (429, 500, 502, 503, 504):
            if attempt == MAX_RETRIES - 1:
                resp.raise_for_status()
            _backoff(attempt, reason=f"HTTP {resp.status_code}")
            continue

        # 4xx other than 429 — don't retry
        resp.raise_for_status()

    return []  # unreachable, but keeps mypy happy


def _backoff(attempt: int, reason: str) -> None:
    wait = INITIAL_BACKOFF * (2 ** attempt)
    print(f"  retry {attempt + 1}/{MAX_RETRIES} after {wait}s ({reason})")
    time.sleep(wait)


def _date_range(start: date, end: date, chunk_days: int):
    """Yield (chunk_start, chunk_end) date pairs covering [start, end)."""
    cursor = start
    while cursor < end:
        chunk_end = min(cursor + timedelta(days=chunk_days), end)
        yield cursor, chunk_end
        cursor = chunk_end


# ── Actuals (FUELHH, fuelType=WIND) ─────────────────────────────────────────

def fetch_actuals(start: date, end: date) -> pd.DataFrame:
    """
    Fetch half-hourly wind generation actuals from FUELHH.

    Parameters
    ----------
    start, end : date
        Settlement date range [start, end) — end is exclusive.

    Returns
    -------
    DataFrame with columns: startTime (datetime64[ns, UTC]), generation (int).
    """
    url = f"{BASE_URL}/datasets/FUELHH/stream"
    rows: list[dict] = []

    for chunk_start, chunk_end in _date_range(start, end, ACTUALS_CHUNK_DAYS):
        # settlementDateTo is inclusive in the API, so subtract 1 day
        params = {
            "settlementDateFrom": chunk_start.isoformat(),
            "settlementDateTo": (chunk_end - timedelta(days=1)).isoformat(),
            "fuelType": "WIND",
        }
        print(f"  FUELHH {params['settlementDateFrom']} → {params['settlementDateTo']}")
        chunk = _get_json(url, params)
        rows.extend(chunk)

    if not rows:
        return pd.DataFrame(columns=["startTime", "generation"])

    df = pd.DataFrame(rows)
    df["startTime"] = pd.to_datetime(df["startTime"], utc=True)
    df = df[["startTime", "generation"]].drop_duplicates(subset="startTime")
    df = df.sort_values("startTime").reset_index(drop=True)
    return df


# ── Forecasts (WINDFOR) ─────────────────────────────────────────────────────

def fetch_forecasts(start: date, end: date) -> pd.DataFrame:
    """
    Fetch wind generation forecasts from WINDFOR.

    Uses publishDateTimeFrom/To so we get *all* historical forecasts,
    not just the latest per slot.

    Parameters
    ----------
    start, end : date
        Publish-time date range [start, end) — end is exclusive.

    Returns
    -------
    DataFrame with columns: startTime, publishTime (datetime64[ns, UTC]),
    generation (int).
    """
    url = f"{BASE_URL}/datasets/WINDFOR/stream"
    rows: list[dict] = []

    for chunk_start, chunk_end in _date_range(start, end, FORECASTS_CHUNK_DAYS):
        params = {
            "publishDateTimeFrom": datetime.combine(chunk_start, datetime.min.time(),
                                                     tzinfo=timezone.utc).isoformat(),
            "publishDateTimeTo": datetime.combine(chunk_end, datetime.min.time(),
                                                   tzinfo=timezone.utc).isoformat(),
        }
        print(f"  WINDFOR publish {chunk_start} → {chunk_end}")
        chunk = _get_json(url, params)
        rows.extend(chunk)

    if not rows:
        return pd.DataFrame(columns=["startTime", "publishTime", "generation"])

    df = pd.DataFrame(rows)
    df["startTime"] = pd.to_datetime(df["startTime"], utc=True)
    df["publishTime"] = pd.to_datetime(df["publishTime"], utc=True)
    df = df[["startTime", "publishTime", "generation"]]
    df = df.drop_duplicates(subset=["startTime", "publishTime"])
    df = df.sort_values(["startTime", "publishTime"]).reset_index(drop=True)
    return df
