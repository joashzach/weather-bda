# Monsoon · Weather Big Data Analytics

A weather analytics dashboard backed by FastAPI and PostgreSQL. Explore weather observations and trends, compare locations, submit and track citizen reports, and use staff tools for moderation and data ingestion.

## Repository layout

```text
frontend/             Dashboard, styles, React animation components, Node server
  dist/               Editable application files and generated motion bundle
  src/                React animation source and third-party license
backend/              FastAPI application, worker, migrations, tests and config
  app/                API routes, services, provider adapters and database models
  alembic/            Database migrations
  config/             Initial location configuration
  tests/              Unit and integration tests
  docs/               API contracts and backend design documentation
docs/                 Historical local acceptance report and source provenance
```

The frontend uses plain JavaScript application modules in `frontend/dist/` alongside React animation components compiled from `frontend/src/`. The build regenerates the motion bundle; it does not regenerate the other application modules. Keep `dist/` in version control.

## Requirements

- Node.js and npm (a current LTS release)
- Python 3.12+
- PostgreSQL 16+

## First-time setup

Clone this repository and install frontend dependencies:

```sh
git clone https://github.com/joshuakevin612/weather_bda.git
cd weather_bda/frontend
npm ci
npm run build
cd ../backend
python -m venv .venv
```

Activate the Python environment:

```powershell
# Windows PowerShell, from backend/
.\.venv\Scripts\Activate.ps1
```

```sh
# macOS / Linux, from backend/
source .venv/bin/activate
```

Install dependencies and copy the configuration template:

```sh
python -m pip install -r requirements-dev.txt
```

Copy `backend/.env.example` to `backend/.env` (`Copy-Item .env.example .env` in PowerShell or `cp .env.example .env` in a Unix shell). Set `DATABASE_URL` and `TEST_DATABASE_URL` to your own PostgreSQL connections. Create the corresponding databases, for example `weather_dev` and `weather_test`, using your PostgreSQL account. The test database name must end in `_test`.

Replace both `JWT_SECRET` and `IP_HASH_SECRET` with independently generated random secrets. To generate one, run `python -c "import secrets; print(secrets.token_hex(32))"`. Set `CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173` to support both local frontend addresses. Keep `.env` private.

From `backend/`, initialize the schema and reference data, then create your own administrator account:

```sh
python -m app.cli check-config
alembic upgrade head
python -m app.cli seed-sources
python -m app.cli seed-locations --file config/locations.yaml
python -m app.cli create-admin --email you@example.com
```

The account command prompts for a password. No shared accounts, credentials, database dumps or provider records are included.

## Run locally

Keep these three terminals running. Activate the Python environment in each backend terminal.

```sh
# Terminal 1 — from backend/
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```sh
# Terminal 2 — from backend/
python -m app.worker
```

```sh
# Terminal 3 — from frontend/
npm run dev
```

- Dashboard: [localhost:5173](http://localhost:5173)
- Interactive API docs: [localhost:8000/docs](http://localhost:8000/docs)
- Readiness: [localhost:8000/health/ready](http://localhost:8000/health/ready)

The API origin is configured in `frontend/dist/config.js`. Stop each service with Ctrl+C.

## Getting data

A fresh database starts without weather observations or citizen reports. Seeded weather sources are disabled by default. Sign in as your administrator, configure and enable a supported source, then queue a manual ingestion run. The worker must be running to process it. Scheduled ingestion remains disabled unless `INGESTION_ENABLED=true` is set. See [backend setup and ingestion documentation](backend/README.md) for details.

Weather from Open-Meteo is model-derived data, not an official station measurement. Citizen reports require human review; news and statistical flags retain their own trust labels. Statistical analysis can show insufficient data until enough baseline history exists. Source attribution and license information are displayed by the application.

## Checks

```sh
# From frontend/
npm run check
npm run lint
npm run build

# From backend/, with its environment activated
python -m compileall -q app
pytest -m "not live"
```

Backend tests require the configured, disposable PostgreSQL test database. They can recreate test tables; never point `TEST_DATABASE_URL` at a development or production database. Live provider tests require explicit configuration and network access.

[Local acceptance report](docs/ACCEPTANCE.md) records earlier validation and its limitations. Referenced screenshots, private QA fixtures and local result files are not part of this repository; the report is historical evidence, not a new test run from a clean clone.

## Deployment

This repository contains the application, not a hosted deployment. Hosting requires a frontend server, API process, worker, PostgreSQL, migrations, HTTPS, private environment configuration and suitable CORS settings. `frontend/server.mjs` binds to loopback for local preview. Adapt serving and process management for your hosting platform, and update the frontend API origin. Never put backend secrets into frontend configuration.

## Source and licenses

See [source provenance](docs/PROVENANCE.md). The included React Bits components retain their license in `frontend/src/reactbits/LICENSE.md` and `frontend/dist/REACT-BITS-LICENSE.txt`. Other packages retain their respective upstream licenses. No additional blanket project license is asserted here.
