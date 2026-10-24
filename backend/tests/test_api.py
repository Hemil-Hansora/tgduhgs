"""
FastAPI TestClient smoke tests for all API endpoints.
"""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    """GET /api/health returns 200 and ok status."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_meta_endpoint():
    """GET /api/meta returns metadata, cutoff config, and available dates."""
    resp = client.get("/api/meta")
    assert resp.status_code == 200
    data = resp.json()
    assert "cutoff_rule" in data
    assert data["cutoff_hour_utc"] == 9
    assert "available_target_days" in data
    assert "total_actual_slots" in data
    assert "total_forecast_rows" in data


def test_forecast_endpoint_valid():
    """GET /api/forecast?target_date=2026-01-15 returns 24 hourly slots."""
    resp = client.get("/api/forecast?target_date=2026-01-15")
    assert resp.status_code == 200
    data = resp.json()
    assert data["target_date"] == "2026-01-15"
    assert data["cutoff_hour_utc"] == 9
    assert data["slots_count"] == 24
    assert len(data["slots"]) == 24

    first_slot = data["slots"][0]
    assert "startTime" in first_slot
    assert "forecast_mw" in first_slot
    assert "publishTime" in first_slot
    assert "cutoff" in first_slot
    assert first_slot["actual_mw"] is not None


def test_forecast_endpoint_invalid_date():
    """GET /api/forecast with malformed date returns 400."""
    resp = client.get("/api/forecast?target_date=invalid-date")
    assert resp.status_code == 400
    assert "Invalid target_date format" in resp.json()["detail"]


def test_accuracy_endpoint_valid():
    """GET /api/accuracy returns summary metrics and series for the requested date window."""
    resp = client.get("/api/accuracy?start=2026-01-10&end=2026-01-15")
    assert resp.status_code == 200
    data = resp.json()
    assert data["start"] == "2026-01-10"
    assert data["end"] == "2026-01-15"

    metrics = data["metrics"]
    assert "mae_mw" in metrics
    assert "rmse_mw" in metrics
    assert "bias_mw" in metrics
    assert "buffer_mw" in metrics
    assert metrics["total_slots"] == 5 * 24

    assert len(data["series"]) == 5 * 24
    slot0 = data["series"][0]
    assert "forecast_mw" in slot0
    assert "actual_mw" in slot0
    assert "error_mw" in slot0


def test_accuracy_endpoint_invalid_dates():
    """GET /api/accuracy with start >= end returns 400."""
    resp = client.get("/api/accuracy?start=2026-01-15&end=2026-01-10")
    assert resp.status_code == 400
    assert "Start date must be strictly before end date" in resp.json()["detail"]


def test_accuracy_horizon_endpoint_valid():
    """GET /api/accuracy/horizon returns lead-time bucket statistics."""
    resp = client.get("/api/accuracy/horizon?start=2026-01-10&end=2026-01-15")
    assert resp.status_code == 200
    data = resp.json()
    assert "buckets" in data
    assert len(data["buckets"]) >= 5

    bucket_names = [b["bucket"] for b in data["buckets"]]
    assert "0-6" in bucket_names
    assert "6-12" in bucket_names
    assert "12-24" in bucket_names
    assert "24-48" in bucket_names
    assert "48+" in bucket_names


def test_range_cap_uncached():
    """Uncached range longer than 7 days returns 400."""
    resp = client.get("/api/accuracy?start=2024-01-01&end=2024-01-15")
    assert resp.status_code == 400
    assert "exceeds limit" in resp.json()["detail"]
