"""
Forecast selection — pick the latest forecast published before the decision cutoff.

The day-ahead power buying team decides on D-1 at 09:00 UTC. For each hourly
target slot on day D, we keep the forecast with the highest publishTime that
is still <= the cutoff. This gives the "best info the buyer had when deciding."
"""

import pandas as pd


def select_forecasts(
    forecasts: pd.DataFrame, cutoff_hour_utc: int = 9
) -> pd.DataFrame:
    """
    For each target slot, select the latest forecast published before the cutoff.

    Cutoff for a target slot on day D = (D-1) at cutoff_hour_utc.
    Only forecasts with publishTime <= cutoff are eligible.
    Among those, the one with the maximum publishTime wins.

    Returns DataFrame with original columns plus 'cutoff'.
    """
    if forecasts.empty:
        out = forecasts.copy()
        if "cutoff" not in out.columns:
            out["cutoff"] = pd.Series(dtype="datetime64[ns, UTC]")
        return out

    f = forecasts.copy()
    target_day = f["startTime"].dt.normalize()
    cutoff = target_day - pd.Timedelta(days=1) + pd.Timedelta(hours=cutoff_hour_utc)
    f["cutoff"] = cutoff

    # Keep only forecasts published at or before the cutoff
    f = f[f["publishTime"] <= f["cutoff"]]

    if f.empty:
        return f

    # For each target slot, take the forecast with the latest publishTime
    f = f.sort_values("publishTime").groupby("startTime", as_index=False).last()
    return f.reset_index(drop=True)


def align_actuals_to_hourly(actuals: pd.DataFrame) -> pd.DataFrame:
    """
    Resample 30-min actuals to hourly by averaging each pair of half-hour slots.

    FUELHH is 30-min, WINDFOR is hourly. We average the :00 and :30 slots
    for each hour so the startTimes align for joining.
    The hourly startTime is the top of the hour (the :00 slot).
    """
    df = actuals.copy()
    # Floor to the hour — both :00 and :30 map to :00
    df["hour"] = df["startTime"].dt.floor("h")
    result = df.groupby("hour", as_index=False)["generation"].mean()
    result = result.rename(columns={"hour": "startTime"})
    return result.reset_index(drop=True)
