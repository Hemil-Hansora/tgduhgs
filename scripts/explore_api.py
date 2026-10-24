"""
Elexon BMRS API Explorer
========================
Fetches one day of FUELHH (WIND) actuals and one day of WINDFOR forecasts.
Prints columns, resolution, row counts, and publishTime-per-startTime stats.

Findings are written to docs/data-notes.md (maintained manually).

Usage:
    python scripts/explore_api.py
"""

import requests
import json
from collections import Counter
from datetime import datetime

BASE = "https://data.elexon.co.uk/bmrs/api/v1"
SAMPLE_DATE = "2026-01-10"


def section(title: str) -> None:
    print(f"\n{'=' * 70}")
    print(title)
    print("=" * 70)


def explore_fuelhh() -> None:
    """Fetch one day of half-hourly wind generation actuals."""
    section("FUELHH stream — wind actuals")

    url = f"{BASE}/datasets/FUELHH/stream"
    params = {
        "settlementDateFrom": SAMPLE_DATE,
        "settlementDateTo": SAMPLE_DATE,
        "fuelType": "WIND",
    }
    print(f"GET {url}")
    print(f"Params: {params}")

    resp = requests.get(url, params=params, timeout=30)
    print(f"Status: {resp.status_code}")
    data = resp.json()
    print(f"Row count: {len(data)}")

    if not data:
        print("⚠ No data returned!")
        return

    print(f"Columns: {list(data[0].keys())}")
    print(f"\nFirst row:\n{json.dumps(data[0], indent=2)}")

    start_times = sorted(set(r["startTime"] for r in data))
    print(f"\nUnique startTimes: {len(start_times)}")

    if len(start_times) >= 2:
        t0 = datetime.fromisoformat(start_times[0].replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(start_times[1].replace("Z", "+00:00"))
        delta_min = (t1 - t0).total_seconds() / 60
        print(f"Resolution: {delta_min:.0f} minutes")

    print(f"Range: {start_times[0]} → {start_times[-1]}")


def explore_windfor() -> None:
    """Fetch one day of wind generation forecasts (by publish time)."""
    section("WINDFOR stream — wind forecasts (filter by publishTime)")

    url = f"{BASE}/datasets/WINDFOR/stream"
    params = {
        "publishDateTimeFrom": f"{SAMPLE_DATE}T00:00:00Z",
        "publishDateTimeTo": f"{SAMPLE_DATE}T23:59:59Z",
    }
    print(f"GET {url}")
    print(f"Params: {params}")

    resp = requests.get(url, params=params, timeout=60)
    print(f"Status: {resp.status_code}")
    data = resp.json()
    print(f"Row count: {len(data)}")

    if not data:
        print("⚠ No data returned!")
        return

    print(f"Columns: {list(data[0].keys())}")
    print(f"\nFirst row:\n{json.dumps(data[0], indent=2)}")

    # Resolution
    start_times = sorted(set(r["startTime"] for r in data))
    print(f"\nUnique target startTimes: {len(start_times)}")
    if len(start_times) >= 2:
        t0 = datetime.fromisoformat(start_times[0].replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(start_times[1].replace("Z", "+00:00"))
        delta_min = (t1 - t0).total_seconds() / 60
        print(f"Resolution: {delta_min:.0f} minutes")
    print(f"Target range: {start_times[0]} → {start_times[-1]}")

    # Publish times
    pub_times = sorted(set(r["publishTime"] for r in data))
    print(f"\nUnique publishTimes: {len(pub_times)}")
    for pt in pub_times:
        print(f"  {pt}")

    # Forecasts per startTime
    counts = Counter(r["startTime"] for r in data)
    vals = list(counts.values())
    print(f"\nForecasts per target startTime:")
    print(f"  min:  {min(vals)}")
    print(f"  max:  {max(vals)}")
    print(f"  mean: {sum(vals) / len(vals):.1f}")

    # Sample slot
    sample_st = start_times[len(start_times) // 2]
    sample_rows = sorted(
        [r for r in data if r["startTime"] == sample_st],
        key=lambda r: r["publishTime"],
    )
    print(f"\nSample target slot {sample_st} ({len(sample_rows)} forecasts):")
    for r in sample_rows:
        print(f"  publishTime={r['publishTime']}  generation={r['generation']} MW")


def explore_windfor_cutoff() -> None:
    """Show forecasts available before the 09:00 cutoff on D-1."""
    section("WINDFOR — forecasts before 09:00 cutoff on Jan 9 (for Jan 10 target)")

    url = f"{BASE}/datasets/WINDFOR/stream"
    params = {
        "publishDateTimeFrom": "2026-01-09T00:00:00Z",
        "publishDateTimeTo": "2026-01-09T08:59:59Z",
    }
    print(f"Params: {params}")

    resp = requests.get(url, params=params, timeout=60)
    data = resp.json()
    print(f"Total rows (all target slots): {len(data)}")

    # Filter to Jan 10 target slots only
    jan10 = [r for r in data if r["startTime"].startswith("2026-01-10")]
    jan10_sts = sorted(set(r["startTime"] for r in jan10))
    print(f"Rows targeting Jan 10: {len(jan10)}")
    print(f"Jan 10 target slots: {len(jan10_sts)}")
    print(f"  range: {jan10_sts[0]} → {jan10_sts[-1]}")

    pub_times = sorted(set(r["publishTime"] for r in jan10))
    print(f"Publish times available before cutoff: {pub_times}")

    counts = Counter(r["startTime"] for r in jan10)
    vals = list(counts.values())
    print(f"Forecasts per slot: min={min(vals)}, max={max(vals)}")


if __name__ == "__main__":
    explore_fuelhh()
    explore_windfor()
    explore_windfor_cutoff()
    print(f"\n{'=' * 70}")
    print("Done. See docs/data-notes.md for written findings.")
    print("=" * 70)
