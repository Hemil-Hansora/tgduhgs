"""
FastAPI application for Wind Forecast Monitoring.

Provides API routes for forecast inspection, accuracy evaluation,
and horizon degradation analysis.
"""

from datetime import date, timedelta
import os
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import CUTOFF_HOUR_UTC
from app.core.horizon import error_by_horizon
from app.core.metrics import compute_metrics
from app.core.selection import align_actuals_to_hourly, select_forecasts
from app.data import DataProvider, RangeExceededError
from app.schemas import (
    AccuracyMetrics,
    AccuracyResponse,
    AccuracySlot,
    ForecastResponse,
    ForecastSlot,
    HealthResponse,
    HorizonBucket,
    HorizonResponse,
    MetaResponse,
)

app = FastAPI(
    title="Wind Forecast Monitoring API",
    description="Elexon BMRS day-ahead wind generation forecasts and accuracy monitoring",
    version="1.0.0",
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global data provider instance
data_provider = DataProvider()


@app.get("/api/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Service health probe."""
    return HealthResponse(status="ok")


@app.get("/api/meta", response_model=MetaResponse)
def get_metadata() -> MetaResponse:
    """Return system configuration, available target dates, and cache stats."""
    forecasts = data_provider.forecasts_df
    actuals = data_provider.actuals_df

    available_days: list[str] = []
    start_str: Optional[str] = None
    end_str: Optional[str] = None

    if not forecasts.empty and "startTime" in forecasts.columns:
        unique_days = sorted(forecasts["startTime"].dt.strftime("%Y-%m-%d").unique())
        available_days = list(unique_days)
        start_str = available_days[0] if available_days else None
        end_str = available_days[-1] if available_days else None

    # Estimate dropped slots across full available cached dataset
    dropped_count = 0
    if not forecasts.empty and not actuals.empty:
        selected = select_forecasts(forecasts, CUTOFF_HOUR_UTC)
        aligned = align_actuals_to_hourly(actuals)
        merged = pd.merge(selected, aligned, on="startTime", how="outer")
        dropped_count = int(
            merged["generation_x"].isna().sum() + merged["generation_y"].isna().sum()
        )

    return MetaResponse(
        cutoff_rule=f"Latest forecast published <= {CUTOFF_HOUR_UTC:02d}:00 UTC on D-1 for delivery on day D",
        cutoff_hour_utc=CUTOFF_HOUR_UTC,
        available_target_start=start_str,
        available_target_end=end_str,
        available_target_days=available_days,
        total_actual_slots=len(actuals),
        total_forecast_rows=len(forecasts),
        dropped_slot_count=dropped_count,
    )


@app.get("/api/forecast", response_model=ForecastResponse)
def get_forecast(
    target_date: str = Query(..., description="Target delivery date (YYYY-MM-DD)"),
) -> ForecastResponse:
    """
    Return selected wind forecast for each hourly delivery slot of target_date.

    Forecasts are selected using the D-1 09:00 UTC gate cutoff rule.
    Hourly actuals are included where available.
    """
    try:
        t_date = date.fromisoformat(target_date)
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid target_date format. Expected YYYY-MM-DD."
        )

    next_date = t_date + timedelta(days=1)

    try:
        forecasts = data_provider.get_forecasts(t_date, next_date)
        actuals = data_provider.get_actuals(t_date, next_date)
    except RangeExceededError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load data: {exc}")

    selected = select_forecasts(forecasts, cutoff_hour_utc=CUTOFF_HOUR_UTC)
    aligned_actuals = (
        align_actuals_to_hourly(actuals) if not actuals.empty else pd.DataFrame()
    )

    if not aligned_actuals.empty:
        merged = pd.merge(
            selected,
            aligned_actuals[["startTime", "generation"]],
            on="startTime",
            how="left",
            suffixes=("", "_actual"),
        )
    else:
        merged = selected.copy()
        merged["generation_actual"] = None

    slots: list[ForecastSlot] = []
    for _, row in merged.iterrows():
        slots.append(
            ForecastSlot(
                startTime=row["startTime"].isoformat(),
                forecast_mw=float(row["generation"]),
                publishTime=row["publishTime"].isoformat(),
                cutoff=row["cutoff"].isoformat(),
                actual_mw=float(row["generation_actual"])
                if pd.notna(row.get("generation_actual"))
                else None,
            )
        )

    earliest_pub = (
        selected["publishTime"].min().isoformat() if not selected.empty else None
    )
    latest_pub = (
        selected["publishTime"].max().isoformat() if not selected.empty else None
    )

    return ForecastResponse(
        target_date=target_date,
        cutoff_hour_utc=CUTOFF_HOUR_UTC,
        earliest_publish_time=earliest_pub,
        latest_publish_time=latest_pub,
        slots_count=len(slots),
        slots=slots,
    )


@app.get("/api/accuracy", response_model=AccuracyResponse)
def get_accuracy(
    start: str = Query(..., description="Start target date YYYY-MM-DD (inclusive)"),
    end: str = Query(..., description="End target date YYYY-MM-DD (exclusive)"),
) -> AccuracyResponse:
    """
    Return accuracy metrics and slot-by-slot errors over the specified target date range.
    """
    try:
        start_d = date.fromisoformat(start)
        end_d = date.fromisoformat(end)
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid date format. Expected YYYY-MM-DD."
        )

    if start_d >= end_d:
        raise HTTPException(
            status_code=400, detail="Start date must be strictly before end date."
        )

    try:
        forecasts = data_provider.get_forecasts(start_d, end_d)
        actuals = data_provider.get_actuals(start_d, end_d)
    except RangeExceededError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load data: {exc}")

    selected = select_forecasts(forecasts, cutoff_hour_utc=CUTOFF_HOUR_UTC)
    aligned_actuals = align_actuals_to_hourly(actuals)

    joined = pd.merge(
        selected[["startTime", "generation"]].rename(
            columns={"generation": "forecast"}
        ),
        aligned_actuals[["startTime", "generation"]].rename(
            columns={"generation": "actual"}
        ),
        on="startTime",
        how="inner",
    )

    metrics_dict = compute_metrics(joined)

    series: list[AccuracySlot] = []
    if not joined.empty:
        for _, row in joined.iterrows():
            f_val = float(row["forecast"])
            a_val = float(row["actual"])
            series.append(
                AccuracySlot(
                    startTime=row["startTime"].isoformat(),
                    forecast_mw=f_val,
                    actual_mw=a_val,
                    error_mw=f_val - a_val,
                )
            )

    return AccuracyResponse(
        start=start,
        end=end,
        metrics=AccuracyMetrics(**metrics_dict),
        series=series,
    )


@app.get("/api/accuracy/horizon", response_model=HorizonResponse)
def get_accuracy_by_horizon(
    start: str = Query(..., description="Start target date YYYY-MM-DD (inclusive)"),
    end: str = Query(..., description="End target date YYYY-MM-DD (exclusive)"),
) -> HorizonResponse:
    """
    Return error metrics bucketed by forecast lead time horizon (hours).

    Evaluates all available forecasts targeting slots within [start, end).
    """
    try:
        start_d = date.fromisoformat(start)
        end_d = date.fromisoformat(end)
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid date format. Expected YYYY-MM-DD."
        )

    if start_d >= end_d:
        raise HTTPException(
            status_code=400, detail="Start date must be strictly before end date."
        )

    try:
        forecasts = data_provider.get_forecasts(start_d, end_d)
        actuals = data_provider.get_actuals(start_d, end_d)
    except RangeExceededError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load data: {exc}")

    aligned_actuals = align_actuals_to_hourly(actuals)
    horizon_df = error_by_horizon(forecasts, aligned_actuals)

    buckets: list[HorizonBucket] = [
        HorizonBucket(
            bucket=row["bucket"],
            mae_mw=float(row["mae_mw"]),
            bias_mw=float(row["bias_mw"]),
            count=int(row["count"]),
        )
        for _, row in horizon_df.iterrows()
    ]

    return HorizonResponse(start=start, end=end, buckets=buckets)


# Serve the built SPA when it is bundled with the app (Vercel container-image
# deploys via Dockerfile.vercel). Guarded by env so the serverless and
# docker-compose deployments keep their nginx/CDN static serving instead.
# The mount is registered last, so all /api/* routes keep priority.
_FRONTEND_DIST = os.getenv("FRONTEND_DIST", "")
if _FRONTEND_DIST and os.path.isdir(_FRONTEND_DIST):
    app.mount(
        "/",
        StaticFiles(directory=_FRONTEND_DIST, html=True),
        name="frontend",
    )
