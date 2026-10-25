# Wind Forecast Monitor (WFM) — Day-Ahead Trading Blotter

An enterprise-grade decision support platform built specifically for a **UK Energy Utility's Day-Ahead Power Buying Team**. The platform ingests national wind generation forecasts and actuals from **Elexon BMRS**, reconstructs the exact forecast vintage available prior to the **09:00 UTC D-1 auction gate cutoff**, evaluates quantitative prediction accuracy, and computes a **statistically defensible safety buffer** for thermal backup procurement.

Scoped to power purchase decisions made throughout **January 2026** (delivery window: **2 Jan 2026 – 1 Feb 2026**).

---

## Table of Contents

1. [Executive Pitch to Client](#1-executive-pitch-to-client-uk-energy-utility)
2. [Technical Architecture Deep Dive for Tech Lead](#2-technical-architecture-deep-dive-for-technical-lead)
3. [10-Minute Video Walkthrough & Presentation Guide](#3-10-minute-video-walkthrough--presentation-guide)
4. [Domain Context, Assumptions & Cutoff Mechanics](#4-domain-context-assumptions--cutoff-mechanics)
5. [Data Sources & Resolution Alignment](#5-data-sources--resolution-alignment)
6. [Quantitative Metrics & Safety Buffer Sizing](#6-quantitative-metrics--safety-buffer-sizing)
7. [Repository & Codebase Layout](#7-repository--codebase-layout)
8. [Quick Start & Local Execution](#8-quick-start--local-execution)
   - [With Docker Compose (Recommended)](#with-docker-compose-recommended)
   - [Local Development (Without Docker)](#local-development-without-docker)
9. [Automated Testing Suite](#9-automated-testing-suite)
10. [Cloud Deployment (Vercel / Docker)](#10-cloud-deployment-vercel--docker)
11. [AI Tools Disclosure](#11-ai-tools-disclosure)

---

## 1. Executive Pitch to Client (UK Energy Utility)

### The Problem
As a day-ahead electricity buyer for a UK energy utility, your core mandate is to serve consumer electricity demand reliably and cost-effectively. Because renewables like wind are intermittent and weather-dependent, you must procure thermal (or interconnector) power in the day-ahead auction to cover the net deficit:
$$\text{Procurement Target} = \text{Demand} - \text{Wind Generation}$$

Crucially, **day-ahead power auction bids close at 09:00 UTC on day $D-1$ for physical delivery throughout day $D$**. When making bids, your traders cannot view future forecasts; they must rely strictly on the forecasts that were published **before the 09:00 UTC cutoff**.

If your desk relies on over-optimistic wind forecasts:
- You **under-buy** in the day-ahead market.
- In the balancing mechanism (or intra-day market), you face severe **system imbalance cash-out prices** (which frequently surge during supply deficits).
- Conversely, systematic under-forecasting leads to over-hedging and unnecessary capital lockup.

### The Solution: Wind Forecast Monitor
Our specialized web application delivers two mission-critical capabilities:

1. **Gate-Closure Forecast Blotter (Forecast View)**:
   - For any target delivery day, the desk instantly views the exact wind generation profile that was visible at auction gate closure.
   - Shows the exact snapshot vintage (e.g. published at 07:30 UTC on $D-1$) alongside the 09:00 UTC cutoff timestamp.
   - Once outturn actuals become available, overlay actual generation curves and inspect hourly slot-by-slot deltas in an interactive table ledger.

2. **Empirical Risk & Accuracy Desk (Accuracy View)**:
   - Quantifies the desk's operational exposure using industry-standard metrics: **MAE** (2,073 MW / 18.1% of mean actual), **RMSE** (2,538 MW), and **Bias** (+1,773 MW over-forecast).
   - **Safety Buffer Recommendation**: Sized directly from the **90th percentile of positive errors (4,402 MW)**. This tells buyers exactly how many megawatts of flexible thermal generation or reserve options to hold to cover 90% of wind shortfall scenarios.
   - **Lead-Time Horizon Degradation**: Demonstrates how forecast uncertainty increases from short horizons (0–6h: 1,687 MW MAE) to day-ahead horizons (24–48h: 2,179 MW MAE), enabling buyers to structure tiered hedges.

---

## 2. Technical Architecture Deep Dive for Technical Lead

### High-Level System Architecture

```
                       ┌──────────────────────────────────────────────┐
                       │           Elexon BMRS Data Streams           │
                       │   - FUELHH (30-min actuals, fuelType=WIND)   │
                       │   - WINDFOR (hourly forecasts, multi-pub)    │
                       └──────────────────────┬───────────────────────┘
                                              │
                         scripts/ingest.py    │ (Pre-ingestion / cache miss)
                                              ▼
                       ┌──────────────────────────────────────────────┐
                       │         data/*.parquet (Snapshot Cache)      │
                       │    - actuals.parquet (1,488 rows)            │
                       │    - forecasts.parquet (18,080 rows)         │
                       └──────────────────────┬───────────────────────┘
                                              │
                                              ▼
                       ┌──────────────────────────────────────────────┐
                       │          FastAPI Backend Service             │
                       │                                              │
                       │  ┌────────────────────────────────────────┐  │
                       │  │   DataProvider (data.py)               │  │
                       │  │   - Cache-first, in-memory DataFrame   │  │
                       │  │   - Fetch-on-miss with 7-day rate cap  │  │
                       │  │   - Transparent parquet persistence    │  │
                       │  └───────────────────┬────────────────────┘  │
                       │                      │                       │
                       │  ┌───────────────────┴────────────────────┐  │
                       │  │   Domain Core Engine (core/)           │  │
                       │  │   - selection.py: D-1 09:00 UTC filter │  │
                       │  │   - metrics.py: MAE, RMSE, P90, Buffer │  │
                       │  │   - horizon.py: error by lead time     │  │
                       │  └───────────────────┬────────────────────┘  │
                       │                      │                       │
                       │  ┌───────────────────┴────────────────────┐  │
                       │  │   REST Routing & Pydantic Validation   │  │
                       │  │   - /api/health, /api/meta             │  │
                       │  │   - /api/forecast, /api/accuracy       │  │
                       │  └───────────────────┬────────────────────┘  │
                       └──────────────────────┼───────────────────────┘
                                              │ JSON over HTTP
                                              ▼
                       ┌──────────────────────────────────────────────┐
                       │     React + Vite + TypeScript Frontend       │
                       │                                              │
                       │  - Design System: "Trading Desk Blotter"     │
                       │  - Recharts: Dual-line, Error & Horizon      │
                       │  - Pages: ForecastPage & AccuracyPage        │
                       │  - Zero client-side computation leaks        │
                       └──────────────────────────────────────────────┘
```

### Architectural Principles

1. **Separation of Pure Domain Logic from Frameworks**:
   - All statistical math and forecast selection algorithms reside in `backend/app/core/` (`selection.py`, `metrics.py`, `horizon.py`).
   - `core/` contains **zero FastAPI imports** and zero I/O dependencies. It operates entirely on typed `pandas` DataFrames, making every business rule unit-testable in isolation with millisecond execution times.

2. **Cache-First Data Layer with Graceful Fetch-on-Miss (`DataProvider`)**:
   - All data access routes request data via `DataProvider.get_actuals(start, end)` and `DataProvider.get_forecasts(start, end)`.
   - The January 2026 baseline ships as committed `.parquet` binary files in `data/`, guaranteeing zero runtime dependence on external Elexon availability for demos and test suites.
   - For un-cached ranges, `DataProvider` fetches missing spans from Elexon, validates against a 7-day maximum live fetch cap (`MAX_LIVE_FETCH_DAYS`), merges new rows into memory, deduplicates, and saves back to disk (`/tmp/data-cache` in serverless).

3. **Time-Aware Horizon Analysis**:
   - Unlike the selected forecast view (which filters strictly by auction cutoff), the horizon analysis leverages **all 18,080 historical forecast snapshots** to evaluate degradation across 5 distinct lead-time windows ($0-6\text{h}$, $6-12\text{h}$, $12-24\text{h}$, $24-48\text{h}$, $48+\text{h}$).

4. **Production Frontend Design System**:
   - Styled using an editorial "Trading Desk Blotter" theme: IBM Plex Sans for legibility, IBM Plex Mono for numeric values, paper surfaces (`#f4f1ea`), hairline borders, and semantic palette (petrol blue for forecast, moss green for actuals, brass for cutoff, rust red for over-forecast).
   - High visual accessibility, full tooltip explanations, responsive mobile/desktop layout, and zero external CSS bloat.

---

## 3. 10-Minute Video Walkthrough & Presentation Guide

For presenting this product on camera or in a client pitch meeting, follow this structured 10-minute cadence:

| Time | Agenda Item | What to Show on Screen | Key Talking Points |
|---|---|---|---|
| **0:00 – 1:30** | **Business Context & Problem Statement** | Slide / App Header | UK Day-Ahead power trading reality: buying decisions happen at 09:00 UTC on $D-1$. Why buying against late or unverified forecasts causes catastrophic cash-out imbalances. |
| **1:30 – 3:30** | **Forecast View & Gate-Closure Selection** | `Forecast view` (e.g. `2026-01-15`) | Walk through the Decision Record: target date, 09:00 UTC cutoff on D-1, vintage snapshot (published at 07:30 UTC). Show the Recharts dual-line curve (forecast vs outturn). Open the **Slot Ledger modal** to show slot-by-slot deltas. |
| **3:30 – 6:00** | **Accuracy View & Risk Buffer Quantification** | `Accuracy view` (Full Jan 2026) | Explain the KPI cards: MAE (2,073 MW / 18.1%), RMSE (2,538 MW), and positive Bias (+1,773 MW). Focus on the **Safety Buffer (4,402 MW)**: explain that P90 of positive errors gives traders a statistically grounded procurement buffer for thermal backup. |
| **6:00 – 7:30** | **Horizon Degradation Analysis** | Accuracy View tabs: `Hourly error` & `Lead-time horizon` | Show the lead-time horizon bar chart. Explain how error increases from 1,687 MW (0–6h) to 2,339 MW (48+h), proving why day-ahead buyers face higher uncertainty than intra-day desks. |
| **7:30 – 9:00** | **Code Architecture & Tech Lead Review** | VS Code / Editor | Highlight `core/selection.py` (the deterministic cutoff algorithm) and `core/metrics.py` (MAPE-safe relative error and buffer sizing). Show the cache-first `DataProvider` and `test_*.py` suite passing 38 tests. |
| **9:00 – 10:00** | **Deployment, Docker & Wrap-up** | Terminal / Browser URL | Show `docker compose up` local execution, Vercel serverless integration, and wrap up with next-step roadmap (weather regime clustering, automated imbalance cost modeling). |

---

## 4. Domain Context, Assumptions & Cutoff Mechanics

### The Cutoff Rule
For delivery on target day $D$:
$$\text{Cutoff Timestamp} = (D - 1) \text{ at } 09:00\text{ UTC}$$

1. In January, the UK operates on Greenwich Mean Time (UTC+0), eliminating daylight saving discrepancies.
2. An Elexon WINDFOR forecast record is eligible for a target slot if and only if:
   $$\text{publishTime} \le \text{Cutoff}$$
3. Among all eligible forecasts targeting that specific delivery slot, the algorithm takes the one with:
   $$\max(\text{publishTime})$$
4. Any forecast published at `09:00:00 UTC` is eligible ($\le$). Any forecast published at `09:00:01 UTC` or later is discarded as post-gate.

### Error Sign Convention
$$\text{Error} = \text{Forecast Generation} - \text{Actual Generation}$$
- **Positive Error ($\text{Error} > 0$)**: **Over-forecast**. The model predicted more wind than actually delivered. The trading desk under-bought in the day-ahead auction and must purchase emergency replacement power at volatile cash-out prices. **This is the primary financial risk direction.**
- **Negative Error ($\text{Error} < 0$)**: **Under-forecast**. Wind outturn exceeded expectations.

---

## 5. Data Sources & Resolution Alignment

| Dataset | Stream Endpoint | Resolution | Target Fields Used |
|---|---|---|---|
| **Actuals (FUELHH)** | `/datasets/FUELHH/stream?fuelType=WIND` | 30 minutes | `startTime`, `generation` (MW) |
| **Forecasts (WINDFOR)** | `/datasets/WINDFOR/stream` | 60 minutes | `startTime`, `publishTime`, `generation` (MW) |

### Time Resolution Alignment Strategy
FUELHH actuals report average generation in 30-minute settlement periods (e.g. `00:00` and `00:30`), whereas WINDFOR forecasts report hourly generation at top-of-hour slots (`00:00`, `01:00`).

To enable rigorous mathematical pairing:
1. Actuals are floored to the hour:
   $$\text{hour} = \text{floor}_{\text{1h}}(\text{startTime})$$
2. For each hourly slot, the two 30-minute actual readings are averaged:
   $$\text{Actual}_{\text{hour}} = \frac{\text{Actual}_{:00} + \text{Actual}_{:30}}{2}$$
3. The resulting aligned series merges seamlessly on `startTime` without synthetic interpolation or distortion of total energy outturn.

---

## 6. Quantitative Metrics & Safety Buffer Sizing

All metrics are computed over the joined valid hourly slots in the selected evaluation window:

1. **Mean Absolute Error (MAE)**:
   $$\text{MAE} = \frac{1}{N} \sum_{i=1}^N |\text{Forecast}_i - \text{Actual}_i|$$
   *January 2026 result: 2,073.3 MW*

2. **Root Mean Square Error (RMSE)**:
   $$\text{RMSE} = \sqrt{\frac{1}{N} \sum_{i=1}^N (\text{Forecast}_i - \text{Actual}_i)^2}$$
   *January 2026 result: 2,538.7 MW*

3. **Forecast Bias (Mean Error)**:
   $$\text{Bias} = \frac{1}{N} \sum_{i=1}^N (\text{Forecast}_i - \text{Actual}_i)$$
   *January 2026 result: +1,773.4 MW* (systematic over-prediction in national wind models during Jan 2026).

4. **Absolute Error Percentiles (P50, P90, P95)**:
   - $P50$: 1,719.8 MW (median deviation)
   - $P90$: 4,167.2 MW (90% of hours had an absolute error under this threshold)
   - $P95$: 5,295.2 MW

5. **Relative Error (% of Mean Actual)**:
   Standard per-slot MAPE ($\frac{|\text{Forecast} - \text{Actual}|}{\text{Actual}}$) explodes to near-infinity when actual wind generation drops near zero on calm days. We adopt the energy-industry standard **aggregate relative MAE**:
   $$\text{MAE \%} = \frac{\text{MAE}}{\frac{1}{N}\sum \text{Actual}_i} \times 100$$
   *January 2026 result: 18.1%*

6. **Safety Buffer Recommendation**:
   $$\text{Buffer} = P_{90}\left(\{\text{Error}_i \mid \text{Error}_i > 0\}\right)$$
   *January 2026 result: 4,402 MW*  
   *Operational Interpretation*: When over-forecasting occurs, 90% of the time the shortfall is less than or equal to 4,402 MW. Power buyers who maintain 4,402 MW of standby thermal capacity or peaking options are protected against 90% of wind deficit shocks.

---

## 7. Repository & Codebase Layout

```
.
├── AGENTS.md                 # Project requirements and engineering specification
├── README.md                 # Complete system documentation (this file)
├── docker-compose.yml        # Multi-container orchestration (backend + frontend)
├── vercel.json               # Vercel serverless deployment config
├── .dockerignore             # Optimized build context filters
├── .gitignore
│
├── data/                     # Committed Parquet Snapshots (Zero-dependency demo)
│   ├── actuals.parquet       # 1,488 rows (Jan 2 – Feb 1, 30-min FUELHH WIND)
│   └── forecasts.parquet     # 18,080 rows (WINDFOR forecasts targeting window)
│
├── scripts/
│   ├── ingest.py             # CLI ingestion: fetch Elexon API -> Parquet
│   └── explore_api.py        # API discovery script used to verify Elexon schemas
│
├── docs/
│   └── data-notes.md         # Field definitions, resolutions, and ingestion notes
│
├── api/                      # Vercel Serverless Function Adapter
│   ├── index.py              # Serverless entrypoint (wraps FastAPI with /tmp cache)
│   └── requirements.txt      # Production runtime dependencies
│
├── backend/                  # FastAPI Application
│   ├── Dockerfile            # Multi-stage Python 3.11 slim build
│   ├── requirements.txt      # Complete dependencies (including test suite)
│   ├── app/
│   │   ├── main.py           # FastAPI router, CORS, schemas, endpoints
│   │   ├── config.py         # Configurable cutoff hour, cache dir, date limits
│   │   ├── schemas.py        # Pydantic models for responses and nested metrics
│   │   ├── data.py           # DataProvider: cache-first & fetch-on-miss
│   │   ├── elexon_client.py  # Elexon BMRS API client with exponential backoff
│   │   └── core/             # Pure mathematical & business logic (Zero-FastAPI)
│   │       ├── selection.py  # Cutoff filter and 30-min to 60-min actuals resampler
│   │       ├── metrics.py    # MAE, RMSE, bias, percentiles, buffer calculator
│   │       └── horizon.py    # Lead-time error bucketing (0-6h, 6-12h, ..., 48+h)
│   └── tests/                # Pytest Suite (38 tests)
│       ├── test_selection.py
│       ├── test_metrics.py
│       ├── test_horizon.py
│       ├── test_data_provider.py
│       └── test_api.py
│
└── frontend/                 # React 19 + TypeScript + Vite SPA
    ├── Dockerfile            # Multi-stage: Node 20 build -> Nginx alpine
    ├── nginx.conf            # Nginx config with reverse proxy for /api
    ├── package.json
    ├── vite.config.ts        # Vite build config with dev API proxy
    └── src/
        ├── main.tsx          # Application entrypoint
        ├── App.tsx           # Layout & tab navigator (Forecast vs Accuracy)
        ├── api.ts            # Typed HTTP client for all backend endpoints
        ├── types.ts          # TypeScript interfaces matching backend schemas
        ├── index.css         # Custom "Trading Desk Blotter" design system
        ├── pages/
        │   ├── ForecastPage.tsx # Date picker, Decision record, Chart & Slot ledger
        │   └── AccuracyPage.tsx # Date presets, 6 KPI cards, 3 Recharts views
        └── components/
            ├── Navbar.tsx
            ├── CutoffBanner.tsx # Gate cutoff & vintage parameters display
            ├── ForecastChart.tsx # Dual line chart (forecast vs outturn)
            ├── AccuracyCharts.tsx # Tabs for forecast vs actual, error, & horizon
            └── MetricCard.tsx   # Stat card with tooltip & plain-language notes
```

---

## 8. Quick Start & Local Execution

### With Docker Compose (Recommended)

To spin up the entire application (Backend + Frontend + Parquet data):

```bash
docker compose up --build
```

- **Frontend Application UI**: http://localhost:3000
- **FastAPI Backend Documentation / OpenAPI**: http://localhost:8001/docs
- **Health Endpoint**: http://localhost:8001/api/health

*(Note: Port 8001 on the host forwards to internal port 8000, preventing port collision with any existing local web services).*

---

### Local Development (Without Docker)

#### Prerequisites
- Python 3.11+
- Node.js 20+ and npm

#### 1. Backend Setup
From the project root:

```bash
# Create and activate virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Start backend server
PYTHONPATH=backend uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
The API is now running at `http://127.0.0.1:8000`.

#### 2. Frontend Setup
In a new terminal window:

```bash
cd frontend

# Install npm dependencies
npm install

# Start Vite development server
npm run dev
```
The web app is accessible at `http://localhost:5173`. Vite automatically proxies `/api` calls to `http://127.0.0.1:8000`.

---

## 9. Automated Testing Suite

The backend contains a rigorous, deterministic test suite covering every core calculation, edge cases, cache mechanics, and API endpoints.

Execute the test suite:

```bash
PYTHONPATH=backend pytest backend/tests/ -v
```

### Test Coverage Highlights (38 Tests Passing)
- **Selection Tests (`test_selection.py`)**:
  - Validates that a forecast published 1 second after 09:00 UTC cutoff is **never chosen**.
  - Verifies that a forecast published exactly at 09:00:00 UTC is **included** ($\le$).
  - Confirms that the latest vintage among valid candidates is consistently chosen.
  - Verifies half-hourly actual averaging logic into top-of-hour slots.
- **Metrics Tests (`test_metrics.py`)**:
  - Validates hand-calculated micro-datasets with known MAE, RMSE, Bias, and percentiles.
  - Confirms zero-division protection on MAPE-safe relative calculation.
  - Verifies safety buffer computation on positive errors.
- **Horizon Tests (`test_horizon.py`)**:
  - Tests boundary conditions ($6\text{h}$ maps to $6-12\text{h}$, $12\text{h}$ maps to $12-24\text{h}$, $>48\text{h}$ maps to $48+\text{h}$).
  - Verifies that horizon analysis aggregates across **all historical forecasts**, not just selected ones.
- **DataProvider Tests (`test_data_provider.py`)**:
  - Cache hits make **zero network requests** (verified with mocks).
  - Cache misses trigger client fetch, persist to parquet, and hit on subsequent calls.
  - Uncached queries exceeding `MAX_LIVE_FETCH_DAYS = 7` raise `RangeExceededError` (HTTP 400).
- **API Smoke Tests (`test_api.py`)**:
  - Smoke tests for `/api/health`, `/api/meta`, `/api/forecast`, `/api/accuracy`, and `/api/accuracy/horizon`.

---

## 10. Cloud Deployment (Vercel / Docker)

The repository is configured for immediate one-click or automated deployment:

### Vercel Deployment (Serverless)
The project includes `vercel.json` configured for a monorepo setup:
- **Build command**: `cd frontend && npm ci && npm run build`
- **Output directory**: `frontend/dist`
- **Rewrites**: `/api/(.*)` $\rightarrow$ `/api`
- **Serverless Python function**: `api/index.py` bundles the committed `data/*.parquet` files and automatically redirects runtime cache storage to `/tmp/data-cache` (the writable directory in AWS Lambda / Vercel execution environments).

To deploy directly with the Vercel CLI:
```bash
npx vercel --prod
```

### Heroku / Container Stack Deployment
The backend `backend/Dockerfile` and `docker-compose.yml` can be deployed directly to container platforms like Heroku Container Registry, AWS ECS, Google Cloud Run, or Render.

---

## 11. AI Tools Disclosure

In compliance with project guidelines and academic/industry transparency standards, this application was developed with the assistance of AI coding tools:

- **AI Tools Used**: Google DeepMind Antigravity CLI paired with Claude 3.7 / Gemini models.
- **Scope of AI Assistance**:
  - Generating initial boilerplate schemas from Elexon BMRS endpoint documentation.
  - Assisting with statistical unit test generation and mathematical test matrices.
  - Crafting responsive CSS tokens for the "Trading Desk Blotter" visual design system.
- **Human Verification & Validation**:
  - Every calculation, cutoff boundary logic ($D-1$ 09:00 UTC), and time-resolution alignment rule was mathematically checked and verified against real Elexon data.
  - All 38 automated test cases were executed and verified locally.
  - Real BMRS queries were validated with `scripts/explore_api.py`.
