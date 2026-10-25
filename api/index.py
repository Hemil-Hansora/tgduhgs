"""
Vercel serverless entry point for the FastAPI backend.

Vercel's Python runtime bundles the whole project, so the existing backend
package and the committed data/ snapshots are available at runtime. This file
only adapts the environment to a read-only serverless filesystem:

- imports the FastAPI app from backend/app (single shared `app` object)
- points CACHE_DIR at /tmp (the only writable path) so DataProvider can
  persist fetch-on-miss parquet merges; committed data/ stays read-only

Env must be set BEFORE importing app.config / app.data because those modules
resolve paths at import time.
"""

import os
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = API_DIR.parent

# Make the `app` package (backend/app) importable
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

# Serverless filesystem is read-only except /tmp
os.environ.setdefault("CACHE_DIR", "/tmp/data-cache")
os.environ.setdefault("MAX_LIVE_FETCH_DAYS", "7")

from app.main import app  # noqa: E402  (import after env setup, on purpose)
