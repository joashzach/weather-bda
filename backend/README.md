# Weather Big Data Analytics Backend

A resilient, audit-compliant backend that collects weather data from public and open-data sources, stores it with full provenance, accepts citizen weather and disaster reports, provides staff moderation workflows, and serves analytics to a React frontend through a versioned REST API.

---

## 1. Quickstart & Local Setup

### Prerequisites
- Python 3.12+
- PostgreSQL 16+

### Exact Setup Commands

```bash
cd backend
python -m venv .venv

# Activate virtual environment:
# On Linux / macOS:
source .venv/bin/activate
# On Windows PowerShell:
.venv\Scripts\Activate.ps1

# Install development dependencies:
pip install -r requirements-dev.txt

# Configure environment variables:
cp .env.example .env
# Edit .env with your PostgreSQL credentials and CSPRNG secrets

# Create databases (via psql or pgAdmin):
psql -U postgres -c 'CREATE DATABASE weather_dev;'
psql -U postgres -c 'CREATE DATABASE weather_test;'

# Apply schema migrations:
alembic upgrade head

# Seed initial reference data (idempotent):
python -m app.cli seed-sources
python -m app.cli seed-locations --file config/locations.yaml

# Create initial administrator user:
python -m app.cli create-admin --email you@example.com

# Start API server (terminal 1):
uvicorn app.main:app --reload --port 8000
# OpenAPI interactive docs will be available at http://localhost:8000/docs

# Start background ingestion worker (terminal 2):
python -m app.worker

# Run linting, formatting check, and test suite:
ruff check . && ruff format --check . && pytest --cov=app
```

---

## 2. PostgreSQL Installation & Role Setup

### Installation
- **Windows**: Download and install PostgreSQL 16 from [postgresql.org/download/windows](https://www.postgresql.org/download/windows/).
- **macOS**: `brew install postgresql@16 && brew services start postgresql@16`
- **Ubuntu/Debian**: `sudo apt update && sudo apt install postgresql-16 postgresql-contrib`

### Creating a Dedicated Database Role
```sql
CREATE ROLE weather_user WITH LOGIN PASSWORD 'your_secure_password';
ALTER ROLE weather_user CREATEDB;
CREATE DATABASE weather_dev OWNER weather_user;
CREATE DATABASE weather_test OWNER weather_user;
```

Update `DATABASE_URL` and `TEST_DATABASE_URL` in `.env`:
```env
DATABASE_URL=postgresql+psycopg://weather_user:your_secure_password@localhost:5432/weather_dev
TEST_DATABASE_URL=postgresql+psycopg://weather_user:your_secure_password@localhost:5432/weather_test
```

---

## 3. Scheduled & Manual Ingestion

- **By default, scheduled ingestion is disabled** (`INGESTION_ENABLED=false`).
- To enable automated background polling:
  1. Set `INGESTION_ENABLED=true` in `.env`.
  2. Verify source credentials (e.g. `DATA_GOV_IN_API_KEY` in `.env`).
  3. Enable and configure desired sources using the Admin API:
     ```http
     PATCH /api/v1/admin/sources/{source_id}
     Authorization: Bearer <ADMIN_TOKEN>
     Content-Type: application/json

     {
       "is_enabled": true,
       "interval_seconds": 3600
     }
     ```
  4. Manual triggers can be queued at any time via:
     ```http
     POST /api/v1/admin/ingestion/{source_name}/run
     Authorization: Bearer <ADMIN_TOKEN>
     ```
     The background worker (`python -m app.worker`) claims queued runs with `SELECT ... FOR UPDATE SKIP LOCKED` and executes them. If the worker is not running, triggered runs remain queued.

---

## 4. Connecting the React Frontend

The React frontend interacts with the backend over versioned REST endpoints:
- **Base URL**: `http://localhost:8000/api/v1`
- **CORS Configuration**: Configure `CORS_ORIGINS` in `.env` to allow your frontend dev server:
  ```env
  CORS_ORIGINS=http://localhost:5173
  ```
- **Attribution Display**: All endpoints return `attribution` metadata (e.g. `source_name`, `trust_level`, `attribution_text`). The frontend must display this attribution alongside data visualizations.

---

## 5. Security Architecture & Quality Gates

- **SSRF Protection**: All outbound calls are validated against private IP ranges, loopback addresses, cloud metadata endpoints, and DNS rebinding attacks via `SafeHttpClient`.
- **RBAC**: Three-tier actor model (`anonymous`, `reviewer`, `admin`) enforced via JWT Bearer tokens and database token revocation.
- **Audit Logging**: Immutable, append-only audit trail for all moderation reviews and source updates.
- **Quality Gates**: Ruff linting, Ruff formatting, and Pytest test coverage (>80% overall, >90% on security modules).
