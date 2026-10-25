"""
Pydantic schemas for the Wind Forecast Monitoring API.

All timestamps are formatted as ISO 8601 UTC strings.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"


class MetaResponse(BaseModel):
    cutoff_rule: str
    cutoff_hour_utc: int
    available_target_start: Optional[str] = None
    available_target_end: Optional[str] = None
    available_target_days: List[str] = Field(default_factory=list)
    total_actual_slots: int
    total_forecast_rows: int
    dropped_slot_count: int


class ForecastSlot(BaseModel):
    startTime: str
    forecast_mw: float
    publishTime: str
    cutoff: str
    actual_mw: Optional[float] = None


class ForecastResponse(BaseModel):
    target_date: str
    cutoff_hour_utc: int
    earliest_publish_time: Optional[str] = None
    latest_publish_time: Optional[str] = None
    slots_count: int
    slots: List[ForecastSlot]


class AccuracySlot(BaseModel):
    startTime: str
    forecast_mw: float
    actual_mw: float
    error_mw: float


class AccuracyMetrics(BaseModel):
    mae_mw: float
    rmse_mw: float
    bias_mw: float
    p50_abs_error_mw: float
    p90_abs_error_mw: float
    p95_abs_error_mw: float
    mae_pct_of_mean_actual: float
    buffer_mw: float
    total_slots: int
    dropped_slots: int


class AccuracyResponse(BaseModel):
    start: str
    end: str
    metrics: AccuracyMetrics
    series: List[AccuracySlot]


class HorizonBucket(BaseModel):
    bucket: str
    mae_mw: float
    bias_mw: float
    count: int


class HorizonResponse(BaseModel):
    start: str
    end: str
    buckets: List[HorizonBucket]
