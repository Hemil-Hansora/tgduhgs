"""
Tests for DataProvider cache behavior, fetch-on-miss, and range limits.
"""

from datetime import date
from unittest.mock import patch
import pandas as pd
import pytest

from app.data import DataProvider, RangeExceededError


@pytest.fixture
def mock_actuals():
    """Mock actuals DataFrame covering 2026-01-10 through 2026-01-12."""
    dates = pd.date_range("2026-01-10 00:00:00", "2026-01-12 23:30:00", freq="30min", tz="UTC")
    return pd.DataFrame({"startTime": dates, "generation": 5000})


@pytest.fixture
def mock_forecasts():
    """Mock forecasts DataFrame covering 2026-01-10 through 2026-01-12."""
    target_dates = pd.date_range("2026-01-10 00:00:00", "2026-01-12 23:00:00", freq="1h", tz="UTC")
    pub_dates = target_dates - pd.Timedelta(hours=15)
    return pd.DataFrame({
        "startTime": target_dates,
        "publishTime": pub_dates,
        "generation": 5200,
    })


def test_cache_hit_does_not_call_client(tmp_path, mock_actuals):
    """When the range is covered by cache, the external client is not called."""
    provider = DataProvider(data_dir=tmp_path, cache_dir=tmp_path, max_live_days=7)
    provider.actuals_df = mock_actuals

    with patch("app.data.client_fetch_actuals") as mock_fetch:
        result = provider.get_actuals(date(2026, 1, 10), date(2026, 1, 12))
        mock_fetch.assert_not_called()
        assert not result.empty
        assert len(result) == 48 * 2


def test_cache_miss_fetches_once_and_caches(tmp_path, mock_actuals):
    """When the range is missing, fetches via client once, saves to cache, hits second time."""
    provider = DataProvider(data_dir=tmp_path, cache_dir=tmp_path, max_live_days=7)
    assert provider.actuals_df.empty

    with patch("app.data.client_fetch_actuals", return_value=mock_actuals) as mock_fetch:
        # First call: cache miss -> calls client
        res1 = provider.get_actuals(date(2026, 1, 10), date(2026, 1, 12))
        assert mock_fetch.call_count == 1
        assert len(res1) == 48 * 2

        # Parquet file was written
        assert (tmp_path / "actuals.parquet").exists()

        # Second call: cache hit -> client NOT called again
        res2 = provider.get_actuals(date(2026, 1, 10), date(2026, 1, 11))
        assert mock_fetch.call_count == 1
        assert len(res2) == 48


def test_range_exceeding_cap_is_rejected(tmp_path):
    """Uncached range longer than MAX_LIVE_FETCH_DAYS raises RangeExceededError."""
    provider = DataProvider(data_dir=tmp_path, cache_dir=tmp_path, max_live_days=7)

    with pytest.raises(RangeExceededError, match="exceeds limit of 7 days"):
        provider.get_actuals(date(2025, 1, 1), date(2025, 1, 15))


def test_invalid_date_order_raises_value_error(tmp_path):
    """Start date >= end date raises ValueError."""
    provider = DataProvider(data_dir=tmp_path, cache_dir=tmp_path, max_live_days=7)

    with pytest.raises(ValueError, match="Start date .* must be before end date"):
        provider.get_actuals(date(2026, 1, 15), date(2026, 1, 10))
