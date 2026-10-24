# AGENTS.md: Wind Forecast Monitoring App

Context file for AI coding agents. Read fully before writing code.

## 1. Goal

Web app for a UK energy utility's day-ahead power buying team. Two jobs:

1. **Forecast view**: for a chosen target day, show the latest wind generation forecast that was available *before the decision cutoff*.
2. **Accuracy view**: compare those forecasts to actual wind generation and quantify the error (MW and %), so buyers can size a safety buffer.

Data: Elexon BMRS only, national wind only. Scope: decisions made in **January 2026**.

Deliverables (for the human, not you): deployed app, public repo with README, 10-min video. Keep the code easy to explain on camera.

## 2. Data sources (verify the exact params against the Elexon docs, don't guess)

| Dataset | Use | Key fields |
|---|---|---|
| FUELHH stream (`fuelType=WIND`) | Actuals | `startTime`, `generation` |
| WINDFOR stream | Forecasts | `startTime` (target), `publishTime`, `generation` |

Docs: https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream and `.../WINDFOR/stream`.

First task: call each endpoint once, print a sample, and confirm field names, time resolution (FUELHH is 30 min; check whether WINDFOR is 30 min or hourly), pagination and date-range limits. Write findings to `docs/data-notes.md`.

## 3. Assumptions (make configurable in `config.py`, document in README)

- **Decision cutoff**: 09:00 UK time on D-1 (day-ahead auction gate closure is around then). In January UK time = UTC, so no DST issue. Config: `CUTOFF_HOUR_UTC = 9`.
- **Decision days**: 1-31 Jan 2026. **Target days**: 2 Jan - 1 Feb 2026 (decision on D-1 for delivery on D).
- **Ingestion window**: actuals for 2 Jan 00:00 - 2 Feb 00:00 UTC. Forecasts with target time in that window, including ones published before January.
- **All timestamps UTC**, stored as timezone-aware.
- **Error = forecast - actual**. Positive = over-forecast (buyer under-buys, the risky direction).
- **Missing data**: if a target slot has no forecast published before the cutoff, or no actual, drop it and report the dropped count in the API response and UI.
- **Forecast selection**: for each target slot, among forecasts with `publishTime <= cutoff(target_day)`, take the one with the max `publishTime`.

## 4. Architecture

```
Elexon API --(scripts/ingest.py, run once)--> data/*.parquet (committed to repo)
                                                   |
                                  FastAPI backend (reads parquet at startup, in memory)
                                                   |  JSON
                                     React + Vite + Recharts frontend
```

- **Data access is cache-first with fetch-on-miss.** All data goes through one `DataProvider` (`backend/app/data.py`) exposing `get_actuals(start, end)` and `get_forecasts(start, end)`. Routes and `core/` never know the source.
  - Jan 2026 (target 2 Jan - 1 Feb) ships as a committed parquet snapshot, so the demo never depends on Elexon being up.
  - Any other range: if not in the cache, fetch from Elexon, merge into the cache, return. Cache dir is configurable (`data/` locally, `/tmp` on Vercel; treat it as ephemeral).
  - Live fetches are capped at `MAX_LIVE_FETCH_DAYS = 7` (Vercel function timeout). Beyond that, return a 400 with a clear message suggesting `scripts/ingest.py`.
  - `scripts/ingest.py --start YYYY-MM-DD --end YYYY-MM-DD` prebuilds any range using the same fetch code as the provider (share one `elexon_client.py`).
  - The Jan 2026 decision window and cutoff stay as config defaults; other ranges use the same cutoff rule.
- **Backend**: Python 3.11, FastAPI, pandas, pytest. Pure logic lives in `core/` (no FastAPI imports) so it is unit-testable.
- **Frontend**: React + Vite + TypeScript, Recharts, plain CSS or Tailwind. Two pages: Forecast and Accuracy.
- **Docker**: one `Dockerfile` for backend, one for frontend (or multi-stage), `docker-compose.yml` for local run.
- **Deploy**: Vercel (frontend as static build; backend as a Vercel Python serverless function with the parquet file bundled). Fallback: Heroku container stack. Watch bundle size limits (pandas); if too big, precompute aggregates at ingest time and serve from JSON/parquet with minimal dependencies.

## 5. Repo layout

```
.
├── AGENTS.md
├── README.md                # files/dirs, how to run, deployed link, AI-tools disclosure
├── docker-compose.yml
├── data/
│   ├── actuals.parquet
│   └── forecasts.parquet
├── scripts/
│   └── ingest.py            # fetch Elexon -> parquet
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py          # FastAPI app, CORS, routes
│   │   ├── config.py        # cutoff hour, date window, data paths
│   │   ├── schemas.py       # pydantic response models
│   │   ├── elexon_client.py # shared Elexon fetch code (pagination, retries)
│   │   ├── data.py          # DataProvider: cache-first, fetch-on-miss
│   │   └── core/
│   │       ├── selection.py # pick latest forecast before cutoff
│   │       ├── metrics.py   # MAE, RMSE, bias, percentiles, MAPE-safe
│   │       └── horizon.py   # error by forecast horizon
│   └── tests/
├── frontend/
│   ├── Dockerfile
│   └── src/
│       ├── pages/ForecastPage.tsx
│       ├── pages/AccuracyPage.tsx
│       ├── components/      # charts, metric cards, date picker
│       └── api.ts
└── docs/data-notes.md
```

## 6. Core logic

```python
# selection.py (sketch)
def select_forecasts(forecasts, cutoff_hour_utc=9):
    # forecasts: startTime, publishTime, generation (UTC, tz-aware)
    f = forecasts.copy()
    target_day = f["startTime"].dt.normalize()
    cutoff = (target_day - pd.Timedelta(days=1)) + pd.Timedelta(hours=cutoff_hour_utc)
    f = f[f["publishTime"] <= cutoff]
    f = f.sort_values("publishTime").groupby("startTime", as_index=False).last()
    f["cutoff"] = cutoff.loc[f.index]  # keep for display
    return f

# join with actuals on startTime, then:
# error = forecast - actual
# horizon_h = (startTime - publishTime) in hours
```

Handle: if WINDFOR is hourly and FUELHH is 30-min, decide an alignment (e.g., resample actuals to hourly mean, or forward-fill the forecast) and document it.

## 7. Metrics (`metrics.py`)

Over the selected slots in the requested range:

- **MAE**, **RMSE**, **bias** (mean error), all in MW
- **Percentiles of absolute error**: P50, P90, P95
- **MAE as % of mean actual generation** (do not use per-slot MAPE; actual near 0 blows it up)
- **Error by horizon**: bucket by `horizon_h` (e.g. 0-6, 6-12, 12-24, 24-48, 48+), report MAE and bias per bucket. This one uses *all* forecasts, not just the selected one.
- **Buffer recommendation**: P90 of positive error (over-forecast), shown as "plan X MW of backup".

## 8. API

| Endpoint | Returns |
|---|---|
| `GET /api/meta` | cutoff rule, available target days, dropped-slot counts |
| `GET /api/forecast?target_date=YYYY-MM-DD` | per slot: `startTime`, selected forecast, `publishTime`, cutoff used, actual (if available) |
| `GET /api/accuracy?start=YYYY-MM-DD&end=YYYY-MM-DD` | metrics + per-slot series (forecast, actual, error) |
| `GET /api/accuracy/horizon?start=...&end=...` | MAE/bias per horizon bucket |
| `GET /api/health` | `{"status": "ok"}` |

Validate dates (400 outside the window). Return ISO 8601 UTC strings.

## 9. UI

- **Forecast page**: date picker, line chart of selected forecast (and actual if the day is past), a visible note "Forecast as of {publishTime range}, cutoff {cutoff}".
- **Accuracy page**: date-range picker, metric cards (MAE, RMSE, bias, P90, buffer), forecast vs actual line chart, error-over-time chart, error-by-horizon bar chart.
- Loading and error states on every chart. Responsive. Clean and minimal; this gets screen-recorded.
- Units always shown (MW, %). Short plain-language tooltip on each metric.

## 10. Tests (pytest)

- `selection`: a forecast published after the cutoff is never chosen; a forecast exactly at the cutoff is included; the latest of several valid ones wins.
- `metrics`: known tiny inputs give exact expected MAE, RMSE, bias.
- `horizon`: bucket assignment edge cases.
- API: one smoke test per endpoint with the TestClient.
- `DataProvider`: cache hit does not call the client (mock it); cache miss fetches once and then caches; a range above `MAX_LIVE_FETCH_DAYS` is rejected.

## 11. Working rules for the agent

- Work in small steps, one milestone at a time. After each, state what changed and how to run it.
- Keep functions short and typed. No clever abstractions; the owner must explain every file on video.
- Do not invent API fields. If unsure, inspect real responses.
- No secrets in the repo. Elexon data endpoints need no key, so don't add one.
- Add a short docstring on each core function explaining the *why* (especially the cutoff logic).
- Don't add features beyond this file without asking.
- Log AI usage notes for the README disclosure.

## 12. Definition of done

- `docker compose up` runs the full app locally.
- Deployed URL works in an incognito window.
- Tests pass. README covers files/dirs, how to start, deployed link, assumptions, AI-tools disclosure.
- Repo name is anonymous (random string).