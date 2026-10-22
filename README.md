# Atmoscope: Weather Big Data Analytics Platform 

A resilient, end-to-end weather analytics and intelligence platform for monitoring meteorological observations, official alerts, open government datasets and crowdsourced citizen incident reports across India.

---

## Table of Contents

1. [System Architecture](#1-system-architecture)
2. [Core Features](#2-core-features)
3. [Technology Stack](#3-technology-stack)
4. [Repository Structure](#4-repository-structure)
5. [Getting Started](#5-getting-started)
6. [Testing and Quality Assurance](#6-testing-and-quality-assurance)
7. [API Reference](#7-api-reference)
8. [Data Sources and Attributions](#8-data-sources-and-attributions)

---

## 1. System Architecture

```mermaid
graph TD
    subgraph Client ["Client Layer"]
        UI["Monsoon Dashboard (React 19 / ESBuild)"]
    end

    subgraph Backend ["Backend Layer (FastAPI / Python 3.12)"]
        API["REST API (/api/v1)"]
        Auth["Auth & RBAC (JWT / Argon2id)"]
        Analytics["Analytics Engine & Anomaly Detector"]
        Worker["Ingestion Worker (APScheduler)"]
        Pipeline["Ingestion Pipeline & Normalizers"]
    end

    subgraph Storage ["Storage Layer"]
        PG[("PostgreSQL 16 (weather_dev / weather_test)")]
    end

    subgraph External ["Data Providers (SSRF Guarded)"]
        OM["Open-Meteo Weather API"]
        IMD["IMD RSS Advisory Feed (Mausam)"]
        DGOV["Data.gov.in Rainfall Datasets"]
        Citizens["Citizen Incident Submissions"]
    end

    UI <-->|JSON over HTTP| API
    API --> Auth
    API --> Analytics
    API <--> PG
    Worker --> Pipeline
    Pipeline --> External
    Pipeline <--> PG
    Citizens -->|POST /reports| API
```

---

## 2. Core Features

### Weather Observations and Forecasts
- Ingests hourly observations and 7-day multi-model meteorological forecasts through **Open-Meteo**.
- Tracks temperature, relative humidity, precipitation, wind speed, gusts and wind direction for major Indian metropolitan hubs: Mumbai, Delhi, Bengaluru, Chennai and Kolkata.

### Official IMD Meteorological Advisories
- Real-time ingestion of live district-level nowcast warnings from the **India Meteorological Department (IMD)** RSS feed.
- Robust parsing of RFC 822 timestamps, converted to UTC with IST offset handling, with sanitized summaries and official Mausam portal links.

### Government Open Datasets (`data.gov.in`)
- Ingestion adapter for Indian meteorological rainfall datasets, with subdivision mapping, flexible query filtering and schema check-constraint validation.

### Citizen Weather Incident Reports
- Crowdsourced hazard reporting (heavy rain, flood, cyclone, heatwave and more) with coordinates, evidence links and anonymous tracking tokens.
- Rate-limited submissions with deduplication and automatic assignment to the nearest location within 50 km.

### Moderation Workflow and Admin Ingestion Monitor
- Staff moderation queue with optimistic locking and audit logging (`pending` → `verified` / `rejected`).
- Admin Ingestion Monitor with manual execution triggers (`Run now`), run logs, error inspection and live source freshness tracking.

### Interactive Frontend (Monsoon Observatory)
- Modern, glassmorphism-inspired interface with dark and light themes.
- Overview KPIs, station comparison tables, SVG metric time-series charts with trend analysis, event breakdowns and a dedicated News Feed.

---

## 3. Technology Stack

| Component | Technologies |
|---|---|
| **Backend API** | Python 3.12, FastAPI, Pydantic v2, SlowAPI (rate limiting) |
| **Database and ORM** | PostgreSQL 16, SQLAlchemy 2.0, Alembic (migrations), Psycopg 3 |
| **Ingestion Engine** | APScheduler, HTTPX, Tenacity (exponential backoff), Feedparser, NH3 |
| **Security** | Argon2id password hashing, PyJWT, SSRF guard, IP hashing salt |
| **Frontend UI** | Node.js, React 19, Vanilla CSS, Motion, GSAP, ESBuild |
| **Testing and QA** | Pytest, Pytest-Cov, Ruff (lint/format), Node Test Runner, ESLint |

---

## 4. Repository Structure

```text
weather-bda/
├── backend/                        # FastAPI backend service
│   ├── alembic/                    # Database migration scripts
│   ├── app/
│   │   ├── analytics/              # Time-series aggregation and anomaly detection
│   │   ├── api/                    # Versioned REST API routers (/api/v1)
│   │   ├── core/                   # Configuration, logging, SSRF guard, rate limits
│   │   ├── db/                     # SQLAlchemy models and session factory
│   │   ├── ingestion/              # Provider adapters (Open-Meteo, RSS, data.gov.in)
│   │   ├── repositories/           # Database repositories (CRUD and upserts)
│   │   ├── schemas/                # Pydantic request and response schemas
│   │   ├── services/               # Business logic (auth, admin, news, reports)
│   │   ├── cli.py                  # Administrative CLI utility
│   │   ├── main.py                 # FastAPI application factory and lifespan
│   │   └── worker.py               # APScheduler background ingestion worker
│   ├── tests/                      # Unit and integration test suites
│   ├── pyproject.toml              # Python build and tool configuration (Ruff / Pytest)
│   └── requirements.txt            # Python dependencies
├── frontend/                       # Node / React dashboard
│   ├── dist/                       # Runnable client assets and bundled modules
│   │   ├── app.js                  # Navigation, state management and layout
│   │   ├── api.js                  # Fetch wrapper, error envelope handling and retry
│   │   ├── features.js             # Analytics, ingestion monitor and moderation queue
│   │   ├── p1.js                   # Weather cards, source freshness and admin forms
│   │   ├── p2.js                   # News feed, location comparison and anomalies
│   │   └── config.js               # API endpoint configuration
│   ├── src/                        # React source components and design tokens
│   ├── server.mjs                  # Local static development server
│   └── package.json                # Frontend scripts and dependencies
└── README.md                       # Project documentation
```

---

## 5. Getting Started

### Prerequisites

- **Python 3.12+**
- **Node.js 20+ (LTS)** and **npm**
- **PostgreSQL 16+**

### Step 1: Database Setup

Make sure PostgreSQL is running locally, then create the development and test databases:

```bash
psql -U postgres -c "CREATE DATABASE weather_dev;"
psql -U postgres -c "CREATE DATABASE weather_test;"
```

### Step 2: Backend Setup

**1. Create and activate a virtual environment**

```powershell
cd backend
python -m venv .venv312
.\.venv312\Scripts\Activate.ps1
```

**2. Install Python dependencies**

```powershell
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

**3. Configure environment variables**

Create a `.env` file in `backend/` (or rely on the defaults in `app/core/config.py`):

```env
ENVIRONMENT=development
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/weather_dev
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/weather_test
JWT_SECRET=supersecretjwtkeyforlocaldevelopmentonlymin32chars
IP_HASH_SECRET=supersecretiphashsecretlocalkeystring
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
INGESTION_ENABLED=true
WORKER_IN_APP=true
DATA_GOV_IN_API_KEY=your_optional_api_key_here
```

**4. Apply database migrations**

```powershell
alembic upgrade head
```

**5. Seed reference locations and data sources**

```powershell
python -m app.cli seed-locations
python -m app.cli seed-sources
```

**6. Create the initial administrator account**

```powershell
python -m app.cli create-admin --email admin@example.com --display-name "System Administrator"
```

You will be prompted to enter and confirm a password.

**7. Start the backend API server**

```powershell
python -m uvicorn app.main:app --reload --port 8000
```

| Resource | URL |
|---|---|
| Interactive OpenAPI docs | http://127.0.0.1:8000/docs |
| Health check (liveness) | http://127.0.0.1:8000/health/live |
| Health check (readiness) | http://127.0.0.1:8000/health/ready |

### Step 3: Frontend Setup

**1. Install dependencies** (in a new terminal)

```powershell
cd frontend
npm ci
```

**2. Start the development server**

```powershell
npm run dev
```

**3. Open the dashboard** at **http://127.0.0.1:5173**

---

## 6. Testing and Quality Assurance

Both the backend and the frontend include automated test suites, syntax linters and type checkers.

### Backend

Run from the `backend/` directory:

```powershell
# 1. Full unit and integration test suite (178 tests)
pytest

# 2. Live external provider ingestion tests (requires Internet connectivity)
pytest -m live

# 3. Code formatting and linting
ruff check .
ruff format --check .
```

### Frontend

Run from the `frontend/` directory:

```powershell
# 1. Automated unit tests (API client, normalization, errors)
npm test

# 2. Syntax validation
npm run check

# 3. ESLint style check
npm run lint

# 4. Rebuild the bundle from React source
npm run build
```

---

## 7. API Reference

All application endpoints are organized under `/api/v1`. System health probes are mounted at the root.

### System Health (root level)

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `GET` | `/health/live` | Public | Process liveness probe (no I/O check) |
| `GET` | `/health/ready` | Public | Readiness probe verifying database connectivity (`SELECT 1`) and Alembic migration alignment |

### Locations and Weather (`/api/v1`)

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `GET` | `/locations` | Public | List active weather monitoring locations (Mumbai, Delhi, Bengaluru, Chennai, Kolkata) |
| `GET` | `/weather` | Public | Paginated weather observations and forecasts with metric, location and date filters |
| `GET` | `/weather/latest` | Public | Latest available observation (`valid_at <= now`) or forecast per active location |
| `GET` | `/weather/{id}` | Public | Retrieve a single weather record by integer ID |

### Analytics and Anomaly Detection (`/api/v1`)

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `GET` | `/analytics/summary` | Public | Aggregated overview KPIs, source freshness status and summary statistics |
| `GET` | `/analytics/timeseries` | Public | Bucketed time-series observations with linear regression trends |
| `GET` | `/analytics/locations` | Public | Comparative weather statistics, data coverage percentage and report counts across stations |
| `GET` | `/analytics/events` | Public | Citizen report hazard event counts grouped by event type, location or day |
| `GET` | `/analytics/anomalies` | Public | Statistical anomaly detection using modified Z-scores against a 30-day baseline |

### Citizen Reports and Advisories (`/api/v1`)

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `GET` | `/news` | Public | Paginated IMD meteorological advisories, nowcasts and alerts |
| `POST` | `/reports` | Public | Submit a citizen incident report (rate-limited; returns a UUID and a secret tracking token) |
| `GET` | `/reports` | Public / Staff | List reports (public callers receive verified reports; staff can view all statuses) |
| `GET` | `/reports/{id}` | Public / Staff | Retrieve a single report (verified reports are public; unverified reports require the `X-Tracking-Token` header or staff authentication) |

### Authentication and Staff Moderation (`/api/v1`)

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `POST` | `/auth/login` | Public | Authenticate staff or admin credentials and receive a JWT bearer token |
| `GET` | `/auth/me` | Authenticated | Inspect the profile and permissions of the current user |
| `POST` | `/auth/change-password` | Authenticated | Change the account password and invalidate existing tokens |
| `GET` | `/admin/reports/pending` | Reviewer / Admin | Moderation queue of unreviewed citizen reports (oldest first) |
| `POST` | `/admin/reports/{id}/review` | Reviewer / Admin | Verify or reject citizen reports with optimistic concurrency (`row_version`) |
| `GET` | `/admin/reports/{id}/reviews` | Reviewer / Admin | Inspect the immutable review audit trail for a report |

### Admin Ingestion Monitor and Data Sources (`/api/v1`)

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `GET` | `/admin/sources` | Admin | List configured data sources, polling intervals and health |
| `PATCH` | `/admin/sources/{id}` | Admin | Update a source's configuration, polling interval or enabled status |
| `POST` | `/admin/ingestion/{source}/run` | Admin | Trigger a manual on-demand ingestion run for any source |
| `GET` | `/admin/ingestion/runs` | Admin | Paginated ingestion run history with status and source filters |
| `GET` | `/admin/ingestion/runs/{id}` | Admin | Detailed execution metrics and sanitized error logs for a run |

---

## 8. Data Sources and Attributions

| Source | Description and license |
|---|---|
| **Open-Meteo** | Weather forecast and historical observation data, provided under the [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/) license. |
| **India Meteorological Department (IMD)** | Meteorological advisories and nowcast warnings provided by the [Ministry of Earth Sciences, Government of India](https://mausam.imd.gov.in/). |
| **Open Government Data Platform India (`data.gov.in`)** | Rainfall datasets published under the [National Data Sharing and Accessibility Policy (NDSAP)](https://data.gov.in/). |
| **Citizen Submissions** | User-submitted incident reports and evidence photographs contributed by community observers. |