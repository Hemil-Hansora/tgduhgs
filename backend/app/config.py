"""
Application configuration for the Wind Forecast Monitoring app.

Provides centralized settings with environment variable overrides.
"""

import os
from datetime import date
from pathlib import Path

# Decision cutoff in UTC (09:00 UK time on D-1; UK is UTC in January)
CUTOFF_HOUR_UTC: int = int(os.getenv("CUTOFF_HOUR_UTC", "9"))

# Maximum date range allowed for on-demand live fetching from Elexon (Vercel timeout guard)
MAX_LIVE_FETCH_DAYS: int = int(os.getenv("MAX_LIVE_FETCH_DAYS", "7"))

# Default project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"

DATA_DIR: Path = Path(os.getenv("DATA_DIR", str(DEFAULT_DATA_DIR)))
CACHE_DIR: Path = Path(os.getenv("CACHE_DIR", str(DATA_DIR)))

# Default decision and target evaluation window (January 2026)
DEFAULT_DECISION_START: date = date(2026, 1, 1)
DEFAULT_DECISION_END: date = date(2026, 1, 31)

DEFAULT_TARGET_START: date = date(2026, 1, 2)
DEFAULT_TARGET_END: date = date(2026, 2, 2)  # exclusive boundary for 1 Feb delivery
