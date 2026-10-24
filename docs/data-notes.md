# Elexon BMRS API — Data Notes

> Findings from `scripts/explore_api.py` and follow-up queries.
> Sample date: 2026-01-10 (settlement date / target day).

---

## Base URL

```
https://data.elexon.co.uk/bmrs/api/v1
```

No API key required. All endpoints are publicly accessible.

---

## FUELHH (Actuals)

**Endpoint:** `GET /datasets/FUELHH/stream`

### Query parameters used

| Param | Example | Notes |
|---|---|---|
| `settlementDateFrom` | `2026-01-10` | yyyy-MM-dd |
| `settlementDateTo` | `2026-01-10` | yyyy-MM-dd |
| `fuelType` | `WIND` | Server-side filter; without it you get all 20 fuel types |
| `publishDateTimeFrom` | ISO 8601 | Alternative to settlementDate; filters by publish time |
| `publishDateTimeTo` | ISO 8601 | |

### Response fields

| Column | Example | Notes |
|---|---|---|
| `dataset` | `"FUELHH"` | Always `FUELHH` |
| `publishTime` | `"2026-01-10T23:30:00Z"` | When the outturn was published (≈ end of the half-hour) |
| `startTime` | `"2026-01-10T23:00:00Z"` | Start of the half-hour settlement period (UTC, ISO 8601) |
| `settlementDate` | `"2026-01-10"` | Trading day |
| `settlementPeriod` | `47` | 1–48 (half-hours in a day) |
| `fuelType` | `"WIND"` | Fuel category |
| `generation` | `8086` | Average generation in MW over the half-hour |

### Key facts

- **Resolution: 30 minutes** (48 rows per day for WIND).
- One row per half-hour per fuel type. No duplicate startTimes for a given fuelType.
- `publishTime` ≈ `startTime + 30 min` (published at the end of each settlement period).
- All 20 fuel types available: BIOMASS, CCGT, COAL, INTELEC, INTEW, INTFR, INTGRNL, INTIFA2, INTIRL, INTNED, INTNEM, INTNSL, INTVKL, NPSHYD, NUCLEAR, OCGT, OIL, OTHER, PS, WIND.
- `generation` is integer MW (no decimals observed).

---

## WINDFOR (Forecasts)

**Endpoint:** `GET /datasets/WINDFOR/stream`

### Query parameters used

| Param | Example | Notes |
|---|---|---|
| `publishDateTimeFrom` | `2026-01-10T00:00:00Z` | Filters by **publish** time — returns all forecasts published in this window |
| `publishDateTimeTo` | `2026-01-10T23:59:59Z` | |
| `from` / `to` | ISO 8601 | Filters by target startTime but returns **only the latest** forecast — not useful for our cutoff logic |
| `settlementDateFrom/To` | `2026-01-10` | Also returns only latest forecast — not useful |

> **Important:** To get *all* historical forecasts (multiple publishTimes per target slot), you **must** filter by `publishDateTimeFrom`/`publishDateTimeTo`. The `from`/`to` and `settlementDate` filters return only the most recently published forecast.

### Response fields

| Column | Example | Notes |
|---|---|---|
| `dataset` | `"WINDFOR"` | Always `WINDFOR` |
| `publishTime` | `"2026-01-10T07:30:00Z"` | When the forecast was published (UTC) |
| `startTime` | `"2026-01-10T12:00:00Z"` | Target delivery slot (UTC) |
| `generation` | `7945` | Forecast wind generation in MW |

### Key facts

- **Resolution: 1 hour** (24 target slots per day — `00:00` to `23:00`).
- Each forecast publication covers a ~73-hour window of target slots (roughly D-1 21:00 to D+2 21:00).
- Forecasts are published **roughly every 2–3 hours**, at irregular times like `02:30`, `04:30`, `07:30`, `09:30`, `11:30`, `15:30`, `18:30`, `22:30` (8 publications observed on the sample day).
- **Multiple forecasts per target slot**: on the sample day, every target hour received exactly **8 forecasts** (one per publish run). For a cutoff window (00:00–09:00), typically **3 forecasts** are available.
- `generation` is integer MW.
- **No `fuelType` or `settlementPeriod` fields** — WINDFOR is wind-only by definition.

---

## Resolution Mismatch

| Dataset | Resolution |
|---|---|
| FUELHH (actuals) | **30 min** (48 slots/day) |
| WINDFOR (forecasts) | **1 hour** (24 slots/day) |

### Alignment strategy

Since WINDFOR is hourly, we will **resample actuals to hourly** by averaging each pair of half-hour slots:

- `startTime 00:00` and `00:30` → hourly slot `00:00`
- `startTime 01:00` and `01:30` → hourly slot `01:00`
- etc.

This gives aligned `startTime` keys for joining forecasts to actuals. Document this in the app and note that actual values shown are hourly averages.

---

## Pagination / Limits

- The `/stream` endpoints return **all matching rows in a single JSON array** (no pagination needed for single-day queries).
- A full day of WINDFOR publishes returns ~584 rows; a full day of FUELHH WIND returns 48 rows. Both are small enough for single requests.
- For multi-day ingestion (31 days), we should chunk by day or by a few days to keep request sizes reasonable. Observed no hard row-count limit on `/stream`, but safer to chunk.

---

## Ingestion Plan

For the Jan 2026 window (target days 2 Jan – 1 Feb):

1. **FUELHH actuals**: fetch `settlementDateFrom=2026-01-02&settlementDateTo=2026-02-01&fuelType=WIND`. Expect ~48 × 31 = 1,488 rows.

2. **WINDFOR forecasts**: need all forecasts with `publishTime` before 09:00 on D-1 for each target day. Safest approach: fetch by `publishDateTimeFrom`/`publishDateTimeTo` in multi-day chunks. Since forecasts can be published days before the target, fetch from roughly 2025-12-29 onwards (a few days before Jan 1) to capture early forecasts for Jan 2 targets.

3. Store both as parquet files in `data/`.

---

## Timestamps

- All timestamps from the API are **UTC, ISO 8601, with `Z` suffix** (e.g., `2026-01-10T07:30:00Z`).
- January UK time = UTC (no DST), so no conversion needed for the cutoff logic.
- We will store all timestamps as timezone-aware UTC `datetime64[ns, UTC]` in pandas / parquet.
