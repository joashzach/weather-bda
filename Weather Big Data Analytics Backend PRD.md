# Weather Big Data Analytics: Backend PRD

*Version 1.0 · Prepared 19 Oct 2026 · Audience: AI coding agent (implementer), backend owner (reviewer), React frontend developer (consumer)*

## 0. Read First: Agent Operating Rules

These rules override anything else in this document if they conflict. MUST, SHOULD and MAY are used in the RFC 2119 sense.

1. **Phase-gated delivery.** Build one phase at a time (Section 12). At the end of each phase, **STOP**, post a Phase Report (template in Appendix B) and **wait for my explicit written approval** (for example, 'Approved, start Phase 3') before touching the next phase. No assumed approval, no 'small prep' for the next phase, no skipping ahead.
2. **Phase 0 is read-only.** Inspect the repository and report. Make no changes in Phase 0.
3. **Preserve others' work.** Work only inside `backend/`, plus `.github/workflows/backend-ci.yml` and small additions to the root `.gitignore` or README that I approve. Never edit, move, reformat or delete the frontend teammate's files. If something conflicts, stop and ask.
4. **Truthful reporting.** Never state that tests, lint, migrations, ingestion or an external integration worked unless you executed it in this session. Include the exact commands run and the real outcome (passed/failed/skipped counts, coverage %). Report failures, skips and known gaps plainly.
5. **No invented provider facts.** Before writing an adapter, read the provider's current official documentation and record the URL, access date, parameters, rate limits and license/attribution terms in `backend/docs/provider-notes.md`. If you cannot verify something (no network, no API key, unclear schema), mark it `UNVERIFIED`, keep that adapter disabled by default and say so in the report. Never fabricate resource IDs, field names, sample 'official' data or successful runs.
6. **No hardcoded responses.** Endpoints return database-backed data only. Fixtures live in `tests/` only. Reference data (`data_sources` rows, default locations) is created by idempotent seed commands, never hidden inside handlers.
7. **No Docker, Kafka, Spark, Kubernetes or Redis** in the repository or the documented setup. (A GitHub Actions Postgres service container for CI is acceptable; see Section 10.)
8. **Secrets.** Never commit secrets, keys, passwords or tokens. `.env` is git-ignored; `.env.example` holds placeholders only.
9. **Green at every gate.** At each phase end: `ruff check`, `ruff format --check` and `pytest` pass; `alembic upgrade head` works on an empty database; `alembic downgrade base` followed by `upgrade head` round-trips.
10. **Git hygiene.** One branch per phase (`backend/phase-N-<slug>`), small conventional commits, no force-push, no merge into the default branch unless I say so.
11. **Scope discipline.** Build all MUST items. Build SHOULD items unless they endanger the phase. Do not build MAY or backlog items unless asked.
12. **Ambiguity.** Use the defaults in Section 15 and list every default you relied on in the Phase Report. Ask a question only when genuinely blocked.

## 1. Product Overview

**Purpose.** A backend that collects weather data from public sources, stores it with full provenance, accepts citizen weather and disaster reports, lets staff verify them, and serves analytics to a React frontend through a versioned REST API.

**Actors.** Anonymous public (read data, submit reports) · Reviewer (verify or reject reports) · Admin (everything, plus sources, ingestion and users) · React frontend (API client only) · Worker (scheduled ingestion).

**MVP goals**

- Reliable ingestion; repeated runs never create duplicates.
- Clear separation of observations vs forecasts, and of official vs model-derived vs news vs citizen information.
- Secure moderation workflow with an immutable audit trail.
- Analytics computed in the database, with optional explainable anomaly flags.
- Runs locally without Docker; deployable to managed hosting with managed PostgreSQL.

**Non-goals (MVP)**: public user accounts or self-registration, file or image upload, push/SMS/email alerts, issuing official warnings, ML forecasting, WebSockets/SSE, multi-tenancy, map tiles.

**Trust model (core principle).** Every weather record, news item and report carries source attribution and a trust class. The API MUST expose it so the frontend can display it.

| Trust class | Origin | Allowed wording |
| --- | --- | --- |
| `official` | Government dataset (data.gov.in) only when the publisher is verifiably an official body | 'official data' |
| `provider_model` | Open-Meteo (model/reanalysis based) | 'model-derived observation' or 'forecast'; never 'station reading', never 'official' |
| `news` | RSS/Atom items | 'news item'; never an observation, never 'verified' |
| `citizen` | Citizen reports | 'pending' until reviewed, 'verified by reviewer' afterwards; never 'official' |

Anomaly flags are always `is_official_warning: false`.

## 2. Technology Decisions

Your suggested stack is accepted. Changes and additions are marked **CHANGE**. The stack is deliberately **synchronous** (sync SQLAlchemy sessions, sync `def` endpoints, sync HTTPX in the worker): simpler transactions, no async/pandas mismatch, ample for MVP load.

| Area | Choice | Notes |
| --- | --- | --- |
| Runtime | Python 3.12 |  |
| Web | FastAPI + Uvicorn | Gunicorn with Uvicorn workers optional in production |
| Database | PostgreSQL 16 (15+ accepted) | timestamptz, JSONB, partial unique indexes, `ON CONFLICT` upserts. No PostGIS in MVP; haversine is enough |
| ORM | SQLAlchemy 2.x typed (`Mapped[]`) + psycopg 3 (`postgresql+psycopg://`) |  |
| Migrations | Alembic with a constraint naming convention | Autogenerate, then hand-review; triggers and partial indexes written by hand |
| Validation/config | Pydantic v2, pydantic-settings |  |
| HTTP client | HTTPX (sync `Client`) + **CHANGE** tenacity | Explicit timeouts, bounded retries with jitter |
| Feeds | feedparser (**parse only**) | **CHANGE**: fetch bytes via the guarded HTTPX client, then hand bytes to feedparser. Never let feedparser open URLs itself (SSRF and size control) |
| HTML sanitising | **CHANGE** nh3 | Strip all markup from RSS titles and summaries |
| Analytics | SQL aggregation (`date_trunc`, `percentile_cont`, `FILTER`) for bulk work; pandas/NumPy only for anomaly detection | Never load whole tables into pandas |
| Auth | PyJWT (HS256) + argon2-cffi |  |
| Rate limiting | SlowAPI (in-memory, per process) + DB-backed account lockout | Documented limitation: counters are per process. Run a single API process in MVP or move to a shared store post-MVP |
| Scheduler | APScheduler 3.x `BlockingScheduler` in a separate worker process | Pin the stable 3.x line; use 4.x only if you verify it is stable |
| Logging | **CHANGE** structlog (JSON) | request\_id, redaction of secrets |
| Testing | pytest, pytest-cov, respx (or `httpx.MockTransport`), time-machine or freezegun | Dedicated test database |
| Quality | Ruff (lint + format); mypy SHOULD (non-blocking in CI) |  |
| Dependencies | `requirements.txt` (runtime), `requirements-dev.txt` | Pin exact versions you actually installed and tested |
| Hosting | Render (web service + background worker + managed Postgres) recommended; Railway is equivalent | Verify current plan limits and pricing at deployment time |

## 3. Architecture

Modular monolith, two processes from one codebase, PostgreSQL as the only coordination channel.

```
React app --HTTPS/JSON--> API process (uvicorn app.main:app) --+
                                                               +--> PostgreSQL
Worker process (python -m app.worker) --adapters--> internet --+
   (Open-Meteo, RSS feeds, data.gov.in)
```

**Layering rules (MUST)**

- `api/` routers: parse and validate input, call one service, map to a response schema. No queries, no business rules.
- `services/`: business rules and transaction boundaries (one transaction per use case).
- `repositories/`: all SQLAlchemy queries. Never commit inside a repository.
- `ingestion/adapters/`: I/O and parsing only. They return normalized Pydantic objects and never import DB code.
- `ingestion/pipeline.py`: the only code that persists adapter output.
- Schemas are separate per audience (`Create`, `Public`, `Staff`). ORM objects are never returned directly. Public schemas are allow-lists.

**Repository layout**

```
backend/
  app/
    main.py            # app factory, middleware, router wiring, CORS, error handlers
    worker.py          # scheduler + queued-run poller
    cli.py             # create-admin, create-user, seed-sources, seed-locations, check-config
    api/               # deps.py, errors.py, health.py, v1/{weather,reports,analytics,auth,news,locations}.py, v1/admin/{reports,ingestion,sources,users}.py
    core/              # config.py, logging.py, security.py, rate_limit.py, http_client.py (SSRF-safe), enums.py
    db/                # base.py, session.py, models/
    schemas/
    services/
    repositories/
    ingestion/         # pipeline.py, scheduler.py, normalizers.py, adapters/{base,open_meteo,rss,data_gov_in}.py
    analytics/         # queries.py, anomaly.py
  alembic/  alembic.ini
  config/locations.example.yaml
  docs/                # provider-notes.md, api-contract.md, frontend-integration.md, deployment.md
  tests/               # unit/, integration/, conftest.py, fixtures/
  pyproject.toml  requirements.txt  requirements-dev.txt  .env.example  .gitignore  README.md
.github/workflows/backend-ci.yml
```

## 4. Data Model

**Conventions (MUST).** All timestamps are `timestamptz` stored and returned in UTC (ISO 8601 with `Z`). Every table has `created_at` (default `now()`); mutable tables also have `updated_at`. Enumerations are `varchar` + `CHECK` (easier to migrate than native enums). Missing measurements are `NULL`, never 0 or sentinel values. Use named constraints and indexes. IDs: `UUID` for users and citizen reports (non-enumerable), `BIGINT identity` for high-volume tables, `INTEGER identity` for small reference tables.

### 4.1 users

`id` UUID PK · `email` varchar(254) (unique index on `lower(email)`) · `display_name` varchar(100) · `password_hash` text (Argon2id) · `role` CHECK in (`admin`,`reviewer`) · `is_active` bool default true · `token_version` int default 0 · `failed_login_count` int default 0 · `locked_until` timestamptz null · `last_login_at` null · timestamps.

### 4.2 data\_sources (reference data, seeded idempotently)

`id` int PK · `name` varchar(50) unique slug (`open_meteo`, `rss_<slug>`, `data_gov_in_<slug>`, `citizen_reports`) · `display_name` · `source_type` CHECK (`weather_api`,`rss`,`open_dataset`,`citizen`) · `adapter_key` · `trust_level` CHECK (`official`,`provider_model`,`news`,`citizen`) · `is_enabled` bool **default false** · `interval_seconds` int CHECK >= 300 · `config` JSONB (non-secret settings only; secrets live in env) · `attribution_text` · `license_url` · `homepage_url` · `last_attempt_at` · `last_success_at` · timestamps.

### 4.3 locations

`id` int PK · `slug` unique · `name` · `region` null · `country_code` char(2) · `latitude` numeric(8,5) CHECK -90..90 · `longitude` numeric(8,5) CHECK -180..180 · `is_active` bool · timestamps. Seeded from `config/locations.yaml` by `seed-locations` (idempotent upsert by slug). Collection is per active location.

### 4.4 weather\_records (observations and forecasts in one table)

| Column | Type / rule |
| --- | --- |
| `id` | bigint PK |
| `location_id`, `source_id` | FK, NOT NULL, `ON DELETE RESTRICT` |
| `record_kind` | CHECK (`observation`,`forecast`) |
| `measurement_basis` | CHECK (`station`,`model_analysis`,`model_forecast`,`unknown`). Open-Meteo past and current values MUST be `model_analysis`, forecasts `model_forecast` |
| `valid_at` | timestamptz: the instant the values describe |
| `issued_at` | timestamptz: forecast fetch/issue time. CHECK: `(record_kind='forecast') = (issued_at IS NOT NULL)` |
| `resolution_seconds` | int (e.g. 3600 hourly, 900 for 15-minute current) |
| `temperature_c` | numeric(5,2), CHECK -90..60 |
| `apparent_temperature_c` | numeric(5,2) null |
| `relative_humidity_pct` | numeric(5,2), CHECK 0..100 |
| `precipitation_mm`, `rain_mm` | numeric(7,2), CHECK >= 0 and <= 1000 (amount over the resolution window) |
| `precipitation_probability_pct` | smallint CHECK 0..100 (forecasts only) |
| `wind_speed_kmh`, `wind_gust_kmh` | numeric(6,2), CHECK >= 0 and <= 500 |
| `wind_direction_deg` | numeric(5,2), CHECK 0..360 |
| `content_hash` | char(64) sha256 of the normalized measurement fields |
| `fetched_at` | timestamptz |
| `ingestion_run_id` | FK to ingestion\_runs, null on delete set null |

**Unique key (deduplication):** `(location_id, source_id, record_kind, valid_at)`. Writes use `INSERT ... ON CONFLICT (...) DO UPDATE ... WHERE weather_records.content_hash IS DISTINCT FROM EXCLUDED.content_hash`. Result classification: new row = inserted, changed hash = updated, unchanged = skipped. Forecasts therefore keep only the latest forecast per `valid_at` (with `issued_at` refreshed); forecast revision history is a backlog item.

**Indexes:** `(location_id, record_kind, valid_at DESC)`, `(source_id, valid_at DESC)`.

**Unit standard (MUST):** °C, %, mm, km/h, degrees, hPa. Request Open-Meteo with explicit unit and `timezone=UTC` parameters and still validate ranges in the normalizer. Out-of-range or non-numeric values are rejected per record and counted as `failed` (never clamped).

### 4.4a Observation vs forecast rules

`record_kind=observation` requires `valid_at <= fetched_at + 15 minutes`. `record_kind=forecast` requires `valid_at > issued_at - 1 hour`. Never mix kinds in one aggregate unless the caller explicitly asks.

### 4.5 citizen\_reports

| Column | Rule |
| --- | --- |
| `id` | UUID PK |
| `event_type` | CHECK in `heavy_rain`, `flood`, `heatwave`, `cold_wave`, `storm`, `cyclone`, `drought`, `landslide`, `lightning`, `hail`, `fog`, `other` |
| `severity` | null or CHECK (`low`,`moderate`,`high`,`extreme`) |
| `description` | text, CHECK length 10..2000 |
| `location_name` | varchar(200) null |
| `latitude`, `longitude` | numeric(8,5), required, range-checked |
| `location_id` | FK null: nearest active location within `REPORT_LOCATION_RADIUS_KM` (default 50), else null |
| `event_time` | timestamptz; not more than 5 minutes in the future and not older than `REPORT_MAX_AGE_DAYS` (default 30) |
| `evidence` | JSONB array, max 5 items of `{type: photo\|video\|link\|other, url: https URL <= 2048, description <= 200}`. Metadata only; the backend NEVER fetches these URLs |
| `contact_email` | varchar(254) null, **private** |
| `status` | CHECK (`pending`,`verified`,`rejected`), default `pending` |
| `submitted_at`, `reviewed_at` | `reviewed_at` null while pending (CHECK) |
| `reviewed_by` | FK users null |
| `ip_hash` | char(64) null: HMAC-SHA256(client IP, `IP_HASH_SECRET`), abuse control only, never returned |
| `tracking_token_hash` | char(64): sha256 of the one-time tracking token returned at submission |
| `row_version` | int default 1, incremented on every status change |

Indexes: `(status, submitted_at)`, `(event_type, status)`, `(location_id, status, event_time DESC)`, `(event_time DESC)`.

### 4.6 report\_reviews (append-only audit)

`id` bigint PK · `report_id` FK RESTRICT · `reviewer_id` FK RESTRICT · `from_status` · `to_status` · `private_notes` text null (<= 2000) · `reason_code` varchar(50) null · `created_at`. A trigger MUST raise an exception on `UPDATE`, `DELETE` and `TRUNCATE`. README MUST document running the app with a DB role that lacks those privileges on this table. Index `(report_id, created_at)`.

### 4.7 news\_items

`id` bigint · `source_id` FK · `dedupe_key` char(64) (sha256 of GUID, else link, else title+published) · `title` varchar(500) · `summary` text (sanitized, <= 2000) · `url` varchar(2048) (http/https only) · `published_at` null · `fetched_at` · `category` CHECK (`news`,`advisory_feed`) · `content_hash`. `UNIQUE(source_id, dedupe_key)`; index `(published_at DESC)`. `is_official` is derived from the source's trust level, never from feed content. Items are never converted into weather observations.

### 4.8 ingestion\_runs

`id` bigint · `source_id` FK · `trigger` CHECK (`scheduled`,`manual`) · `triggered_by` FK users null · `status` CHECK (`queued`,`running`,`succeeded`,`partial`,`failed`,`abandoned`) · `queued_at` · `started_at` · `finished_at` · `records_fetched`, `inserted`, `updated`, `skipped`, `failed` (ints >= 0) · `error_summary` varchar(1000) (sanitized) · `details` JSONB (per-location or per-entry sanitized errors, truncated to 50 entries). **Overlap prevention:** `CREATE UNIQUE INDEX ... ON ingestion_runs (source_id) WHERE status IN ('queued','running')`.

### 4.9 audit\_events (append-only, same trigger protection)

`id` bigint · `actor_user_id` null · `action` varchar(64) (`auth.login_success`, `auth.login_failed`, `user.created`, `source.updated`, `ingestion.manual_trigger`, `report.reviewed`) · `entity_type` · `entity_id` · `metadata` JSONB (no secrets, no tokens, no notes) · `ip_hash` null · `created_at`.

### 4.10 Relationships

`data_sources 1-N weather_records, news_items, ingestion_runs` · `locations 1-N weather_records, citizen_reports` · `users 1-N report_reviews, ingestion_runs(triggered_by)` · `citizen_reports 1-N report_reviews`. Retention and partitioning of `weather_records` are backlog items; design the indexes so they remain possible.

## 5. Configuration and Secrets

All configuration comes from environment variables via a single `Settings` class (pydantic-settings). `.env.example` lists every variable with a placeholder and a comment. `python -m app.cli check-config` validates settings and exits non-zero on problems, without printing secrets.

| Variable | Default / rule |
| --- | --- |
| `ENVIRONMENT` | `development`, `test` or `production` |
| `DATABASE_URL` | `postgresql+psycopg://user:pass@localhost:5432/weather_dev` |
| `TEST_DATABASE_URL` | Separate database (name must end in `_test`; the test suite refuses to run otherwise) |
| `JWT_SECRET` | At least 32 random characters. Startup MUST fail in production if missing, short, or equal to the example value |
| `JWT_ISSUER`, `JWT_AUDIENCE` | Validated on every token |
| `ACCESS_TOKEN_TTL_MINUTES` | 30 |
| `CORS_ORIGINS` | Comma-separated explicit origins, default `http://localhost:5173`. A wildcard is rejected at startup |
| `IP_HASH_SECRET` | Random secret for HMAC of client IPs |
| `API_DOCS_ENABLED` | `true` in development; configurable in production |
| `TRUSTED_PROXY_IPS` | Proxies whose `X-Forwarded-For` is honoured (empty in development) |
| `ALLOWED_SOURCE_HOSTS` | Comma-separated hostname allow-list for all outbound source requests |
| `INGESTION_ENABLED` | **`false` by default.** Master switch for scheduled jobs in the worker |
| `INGESTION_RUN_TIMEOUT_SECONDS` | 900 |
| `HTTP_CONNECT_TIMEOUT`, `HTTP_READ_TIMEOUT` | 5 s, 15 s |
| `HTTP_MAX_RETRIES`, `HTTP_MAX_RESPONSE_BYTES` | 3, 5 MB |
| `OPEN_METEO_BASE_URL`, `OPEN_METEO_FORECAST_DAYS`, `OPEN_METEO_PAST_DAYS` | Provider defaults verified in Phase 2 |
| `DATA_GOV_IN_API_KEY` | Empty means the adapter reports 'not configured' and cannot run |
| `RATE_LIMIT_LOGIN`, `RATE_LIMIT_REPORT_SUBMIT`, `RATE_LIMIT_PUBLIC_READ`, `RATE_LIMIT_TRACKING` | `5/minute`, `5/hour`, `120/minute`, `20/minute` |
| `LOGIN_LOCKOUT_THRESHOLD`, `LOGIN_LOCKOUT_MINUTES` | 5, 15 |
| `REPORT_LOCATION_RADIUS_KM`, `REPORT_MAX_AGE_DAYS` | 50, 30 |
| `LOG_LEVEL` | `INFO` |

**Administrator bootstrap (MUST).** No default or hardcoded credentials anywhere. `python -m app.cli create-admin --email <email>` prompts for the password with `getpass` (or reads it with `--password-stdin`), enforces a minimum of 12 characters, hashes with Argon2id, and refuses to run if an admin already exists unless `--allow-additional`. Reviewers are created with `python -m app.cli create-user --role reviewer`. No endpoint creates the first admin.

## 6. Security Requirements

### 6.1 Authentication

- `POST /api/v1/auth/login` accepts JSON `{email, password}` and returns a short-lived JWT access token. No refresh tokens in MVP; the frontend sends the user back to login on expiry.
- Argon2id via argon2-cffi defaults (tunable by config). On successful login, rehash if `check_needs_rehash` says so.
- JWT (HS256) claims: `sub` (user id), `role`, `iat`, `exp`, `iss`, `aud`, `jti`, `tv` (token\_version). Reject tokens with missing or wrong claims, expired tokens, or `tv` different from the user's current `token_version`. Load the user from the database on every authenticated request and reject inactive users. Pin the algorithm list when decoding; never accept `none`.
- No user enumeration: unknown email, wrong password, inactive user and locked account all return the same `401` message and take similar time (verify against a dummy hash when the user does not exist).
- Account lockout: after `LOGIN_LOCKOUT_THRESHOLD` consecutive failures set `locked_until`; reset the counter on success. Lockout is stored in the database so it works across processes.
- SHOULD: `POST /api/v1/auth/change-password` (requires current password) which increments `token_version`, invalidating all earlier tokens.
- Tokens and passwords MUST NOT be logged, stored in audit metadata or echoed in errors.

### 6.2 Role-based access control

| Capability | Anonymous | Reviewer | Admin |
| --- | --- | --- | --- |
| Read weather, locations, news, public analytics | Yes | Yes | Yes |
| Submit report | Yes (rate limited) | Yes | Yes |
| Read verified reports | Yes | Yes | Yes |
| Read pending/rejected reports, `status` filter | No | Yes | Yes |
| Review report (pending to verified/rejected) | No | Yes | Yes |
| Retract verified report, reopen rejected report | No | No | Yes |
| Read review history with private notes | No | Yes | Yes |
| Ingestion runs, trigger ingestion, sources | No | No | Yes |
| Full analytics status breakdown | No | Yes | Yes |

Implement as reusable FastAPI dependencies (`require_role(...)`) and test every row of this matrix, both the allowed and the denied side.

### 6.3 Rate limiting

| Target | Limit (configurable) | Key |
| --- | --- | --- |
| `POST /auth/login` | 5/minute | client IP (plus per-account lockout) |
| `POST /reports` | 5/hour | client IP |
| `GET /reports/{id}` with tracking token | 20/minute | client IP |
| Other public reads | 120/minute | client IP |
| Authenticated admin routes | 120/minute | user id |

Return `429` with the standard error envelope and a `Retry-After` header. Client IP must be derived safely: use `X-Forwarded-For` only when the direct peer is in `TRUSTED_PROXY_IPS`. Document the per-process limitation. Rate limiting MUST be switchable off only in the test environment.

### 6.4 Outbound requests and SSRF (MUST)

All source fetching goes through one `core/http_client.py` factory that enforces:

- `https` only (plain `http` only when `ENVIRONMENT=development` and the host is explicitly allowed).
- Hostname must be in `ALLOWED_SOURCE_HOSTS`; URLs with credentials, unusual ports or IP-literal hosts are rejected.
- DNS resolution check: reject loopback, private, link-local (including cloud metadata `169.254.0.0/16`), multicast and reserved addresses, for IPv4 and IPv6. Re-check on every redirect.
- Redirects: disabled by default; if enabled, at most 3 and each hop revalidated.
- Connect and read timeouts, total response size cap (`HTTP_MAX_RESPONSE_BYTES`, enforced while streaming), content-type check, and a fixed `User-Agent` that identifies the project.
- Users never supply URLs that the backend fetches. Citizen evidence URLs are stored, never fetched. Source URLs can change only through admin `PATCH` and still pass all the checks above.

### 6.5 Input validation and injection

- All SQL goes through SQLAlchemy with bound parameters. No string-built SQL. Sort fields and filter names use allow-lists.
- Request schemas use `extra='forbid'`, trimmed strings, explicit max lengths, enum types and range checks. Control characters are stripped from free text. Public JSON bodies are capped at 64 KB.
- Pagination `limit` is capped (default 50, max 200; weather max 500). Date ranges are capped (Section 7.1).
- Output is JSON only; the API never renders HTML. RSS text is sanitized with nh3 before storage.

### 6.6 Privacy

- `contact_email`, `ip_hash`, `tracking_token_hash`, `private_notes` and `reviewer_id` never appear in public responses (tested with an automated 'forbidden keys' check on every public schema).
- Staff responses include `contact_email`; it is never logged.
- A non-public report requested without authorization returns `404` (not `403`) so existence is not leaked.
- Public report responses omit evidence URLs (type, description and a `has_link` flag only). Staff see the URLs. Hosting or proxying evidence is a backlog item.

### 6.7 CORS, headers, errors, logging

- CORS: explicit `CORS_ORIGINS`, methods `GET, POST, PATCH, OPTIONS`, headers `Authorization, Content-Type, X-Tracking-Token, X-Request-ID`, `allow_credentials=False` (Bearer header auth, no cookies).
- SHOULD set `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, and `Cache-Control: no-store` on `/auth` and `/admin` responses. HTTPS and HSTS are handled by the hosting platform; document it.
- Unhandled exceptions return a generic `500` envelope with `request_id`; stack traces go to logs only, never to clients.
- Logging: structlog JSON to stdout with `timestamp`, `level`, `event`, `request_id`, `method`, `path`, `status`, `duration_ms`, `user_id` (if any). Never log request bodies, `Authorization`, passwords, tokens, emails, notes or full IPs. Add a redaction processor and a test that proves a token and a password do not appear in captured logs.
- SHOULD: run the application with a least-privilege database role; run migrations with a separate owner role.

## 7. REST API Specification

### 7.1 Conventions (MUST)

- Base path `/api/v1`; health endpoints are at the root (`/health/live`, `/health/ready`). JSON only, `snake_case` fields, UTC ISO 8601 timestamps with `Z`. IDs are strings in JSON for UUIDs and numbers for integers.
- Auth: `Authorization: Bearer <jwt>`.
- **Error envelope** for every non-2xx response, including validation, auth, rate-limit and unexpected errors:

```
{ 'error': { 'code': 'validation_error', 'message': 'Human readable summary', 'details': [ { 'field': 'latitude', 'issue': 'must be between -90 and 90' } ], 'request_id': 'b1f0...' } }
```

| HTTP | `code` | Use |
| --- | --- | --- |
| 400 | `bad_request` | Malformed request |
| 401 | `unauthorized` | Missing, invalid or expired token; bad login |
| 403 | `forbidden` | Authenticated but role or action not permitted |
| 404 | `not_found` | Missing or non-visible resource |
| 409 | `conflict`, `invalid_transition`, `stale_version`, `already_running`, `source_not_configured` | State conflicts |
| 413 | `payload_too_large` | Body over limit |
| 422 | `validation_error` | Schema or range validation (FastAPI errors are remapped into the envelope) |
| 429 | `rate_limited` | With `Retry-After` |
| 500 | `internal_error` | Generic |
| 503 | `service_unavailable` | Readiness failure |

- **Pagination** on every list endpoint: query `limit` (default 50, max 200) and `offset` (default 0). Response `{ 'items': [...], 'total': N, 'limit': 50, 'offset': 0 }`. Sorting uses `sort=<field>` or `sort=-<field>` from a per-endpoint allow-list. Ordering MUST be deterministic (tie-break on id).
- **Time filters:** `from` and `to` are inclusive/exclusive (`from <= t < to`) ISO 8601 instants; naive timestamps are rejected; `from < to`; maximum span 31 days for raw record lists and 366 days for aggregates.
- OpenAPI: every route has `summary`, tags, documented response models, error responses (401/403/404/409/422/429 as applicable) and at least one example. Declare the Bearer security scheme so Swagger's Authorize works. Group tags: Health, Weather, Reports, Analytics, News, Auth, Admin.

### 7.2 Endpoint catalogue

| Method and path | Auth | Purpose |
| --- | --- | --- |
| `GET /health/live` | none | Process liveness. No DB access. `200 {status:'ok'}` |
| `GET /health/ready` | none | `SELECT 1` and Alembic head check. `200` or `503 {status:'unavailable', checks:{database:'ok/fail', migrations:'ok/fail'}}`, no error text |
| `GET /api/v1/locations` | none | Active locations (`{items:[{id,slug,name,region,country_code,latitude,longitude}]}`) |
| `GET /api/v1/weather` | none | List records (filters below) |
| `GET /api/v1/weather/latest` | none | Latest record per active location |
| `GET /api/v1/weather/{observation_id}` | none | One record by id (any kind; the `kind` field says which) |
| `GET /api/v1/news` | none | RSS/Atom items (filters: `source`, `from`, `to`, `category`) |
| `POST /api/v1/reports` | none, rate limited | Submit a report |
| `GET /api/v1/reports` | none (staff optional) | List reports |
| `GET /api/v1/reports/{report_id}` | none, staff, or tracking token | One report |
| `GET /api/v1/analytics/summary` `timeseries` `locations` `events` | none (staff gets more) | Section 9 |
| `POST /api/v1/auth/login` | none, rate limited | Obtain token |
| `GET /api/v1/auth/me` | any role | Current user |
| `GET /api/v1/admin/reports/pending` | reviewer, admin | Moderation queue |
| `GET /api/v1/admin/reports/{report_id}/reviews` | reviewer, admin | Review history with private notes |
| `POST /api/v1/admin/reports/{report_id}/review` | reviewer, admin (some transitions admin only) | Verify, reject or reopen |
| `GET /api/v1/admin/ingestion/runs` and `/{run_id}` | admin | Run history and detail |
| `POST /api/v1/admin/ingestion/{source_name}/run` | admin | Queue a manual run |
| `GET /api/v1/admin/sources` and `PATCH /{source_id}` | admin | Inspect and configure sources |

The `news`, `locations` and `reviews` endpoints are additions to your list; the frontend cannot work without them. MAY: `POST /api/v1/admin/users` to create reviewers (the CLI is the MUST).

### 7.3 Weather

**`GET /weather`** query: `location_id` (int), `kind` (`observation` default, `forecast`, or `all`), `source` (source name), `from`, `to`, `sort` (`valid_at` or `-valid_at`, default `-valid_at`), `limit`, `offset`. Defaults when `from`/`to` are omitted: observations cover the last 24 hours; forecasts cover now to +72 hours. Unknown `location_id` returns `404`; invalid filters `422`.

`WeatherRecord`: `id`, `kind`, `valid_at`, `issued_at` (null for observations), `fetched_at`, `measurement_basis`, `resolution_seconds`, `location {id, slug, name}`, `source {name, display_name, trust_level, attribution_text}`, and a `measurements` object with `temperature_c`, `apparent_temperature_c`, `relative_humidity_pct`, `precipitation_mm`, `rain_mm`, `precipitation_probability_pct`, `wind_speed_kmh`, `wind_gust_kmh`, `wind_direction_deg`. Any measurement may be `null`, which means 'not provided', never zero.

**`GET /weather/latest`** query: `location_id` optional, `kind` (default `observation`). Returns `{ 'as_of': <now>, 'items': [WeatherRecord] }` with the newest observation with `valid_at <= now` per location (for `kind=forecast`, the earliest forecast with `valid_at >= now`). Locations without data are listed in `missing_location_ids` rather than faked. Declare this route before `/{observation_id}`.

**`GET /weather/{observation_id}`**: integer path parameter; `404` if absent.

### 7.4 Reports

**`POST /reports`** body (`extra='forbid'`, so a client-supplied `status` is a `422`): `event_type` (enum), `severity` (optional enum), `description` (10..2000), `location_name` (optional, <= 200), `latitude`, `longitude`, `event_time`, `evidence` (optional, max 5, each `{type, url, description}`), `contact_email` (optional, valid email). The server always sets `status='pending'`, assigns `location_id`, hashes the IP, and generates a 32-byte URL-safe `tracking_token`. Response `201`: `{ id, status:'pending', submitted_at, tracking_token }`. The token is shown **once**; only its hash is stored. SHOULD: reject exact duplicate submissions (same `ip_hash` and description fingerprint within 1 hour) with `409`.

**`GET /reports`** public query: `event_type`, `location_id`, `from`/`to` (on `event_time`), `sort` (`event_time`, `submitted_at`; default `-event_time`), `limit`, `offset`. Anonymous callers receive **verified reports only**. A `status` parameter (`pending`, `verified`, `rejected`, `all`) is accepted only with a staff token; otherwise `403`. Public schema: `id`, `event_type`, `severity`, `description`, `location_name`, `latitude`, `longitude`, `location` (or null), `event_time`, `evidence` (`type`, `description`, `has_link` only), `status`, `submitted_at`, `reviewed_at`. Staff schema adds `contact_email`, `evidence[].url`, `row_version`, `reviewed_by {id, display_name}`.

**`GET /reports/{report_id}`**: UUID. Verified: visible to everyone. Otherwise visible only to staff, or to the submitter presenting the matching `X-Tracking-Token` header (compared in constant time; the response then contains the public fields plus `status` and `reviewed_at` and never notes). Any other case: `404`.

### 7.5 Authentication endpoints

`POST /auth/login` request `{email, password}`; `200 {access_token, token_type:'bearer', expires_in, user:{id, email, display_name, role}}`; `401` generic on any failure; `429` on rate limit. `GET /auth/me` returns the same `user` object.

### 7.6 Administration

**`GET /admin/reports/pending`**: staff schema, oldest first by default, filters `event_type`, `location_id`, `from`, `to`.

**`POST /admin/reports/{report_id}/review`** body `{ decision: 'verify' | 'reject' | 'reopen', notes?: string<=2000, reason_code?: string<=50, expected_row_version: int }`.

Valid transitions (anything else returns `409 invalid_transition`):

| From | Decision | To | Who | Notes required |
| --- | --- | --- | --- | --- |
| `pending` | `verify` | `verified` | reviewer, admin | no |
| `pending` | `reject` | `rejected` | reviewer, admin | yes (notes or reason\_code) |
| `verified` | `reject` (retraction) | `rejected` | admin | yes |
| `rejected` | `reopen` | `pending` | admin | yes |

In **one transaction**: `SELECT ... FOR UPDATE` the report, compare `expected_row_version` (`409 stale_version` on mismatch), validate the transition and role, insert the immutable `report_reviews` row, update `status`, `reviewed_at`, `reviewed_by`, `row_version`, and write an `audit_events` row. Response `200`: staff report. The notes appear only in `GET /admin/reports/{id}/reviews` (`{items:[{id, reviewer{id,display_name}, from_status, to_status, reason_code, private_notes, created_at}]}`).

**`POST /admin/ingestion/{source_name}/run`**: inserts a `queued` run and returns `202 {run_id, status:'queued'}`. `404` unknown source; `409 already_running` if a queued or running run exists for the source (enforced by the partial unique index, so it is race-safe); `409 source_not_configured` if the adapter's `is_configured()` check fails. The API process never runs ingestion itself; the worker picks up queued runs (Section 8.5).

**`GET /admin/ingestion/runs`** filters `source`, `status`, `from`, `to`, standard pagination. **`/runs/{run_id}`** adds `details` (sanitized).

**`GET /admin/sources`** lists sources with `is_enabled`, `interval_seconds`, `trust_level`, `last_attempt_at`, `last_success_at`, `configured` (bool) and the last run summary. **`PATCH /admin/sources/{source_id}`** accepts only `is_enabled`, `interval_seconds` (300..86400), `display_name`, `attribution_text`, and `config` (validated by the adapter's own Pydantic config model; URL values pass the SSRF rules). `name`, `adapter_key` and `trust_level` cannot change through the API. Enabling a source that is not configured returns `409 source_not_configured`. Every change is audited.

## 8. Ingestion and Processing

### 8.1 Pipeline (MUST)

One reusable pipeline for every adapter: **fetch, validate and normalize, deduplicate, save, count, finalize**.

- Adapter contract (`ingestion/adapters/base.py`): `key`, `is_configured(source, settings) -> bool`, `run(source, targets, http) -> AdapterResult` where `AdapterResult` holds normalized Pydantic records, per-record or per-target errors, and `fetched_count`. Adapters never touch the database.
- The pipeline persists each target (location or feed) in its **own transaction**. One failing location or feed never aborts the others (failure isolation).
- Counters: `records_fetched`, `inserted`, `updated`, `skipped` (valid but unchanged or unmatched), `failed` (invalid or unsaved).
- Final status: `succeeded` (no failures), `partial` (some targets or records failed, some saved), `failed` (nothing saved or fatal error). `last_attempt_at` is always updated; `last_success_at` only for `succeeded` and `partial`.
- **Sanitized errors:** store an error code and short message only. Strip URLs' query strings, API keys, tokens, response bodies and stack traces; truncate to 1000 characters. Full detail goes to logs with the same redaction.
- Normalizers are pure functions with unit tests: unit conversion, range validation, `None` for missing, UTC parsing (naive timestamps rejected). Invalid values are rejected and counted, never clamped or guessed.

### 8.2 Open-Meteo adapter (Phase 2)

Verify against the current official documentation before coding (Rule 5) and record findings in `docs/provider-notes.md`: endpoints, variable names, unit parameters, `timezone` and time format options, `past_days` and `forecast_days` limits, rate limits, the non-commercial/commercial terms, and the attribution requirement. Variables expected (verify): `temperature_2m`, `apparent_temperature`, `relative_humidity_2m`, `precipitation`, `rain`, `precipitation_probability`, `wind_speed_10m`, `wind_gusts_10m`, `wind_direction_10m`.

- One HTTP request per active location (isolates failures). Request `timezone=UTC`, and explicit units for temperature, wind speed and precipitation.
- **Observation vs forecast split:** hourly values with `valid_at` at or before the current hour (floor of `fetched_at`) become `record_kind='observation'` with `measurement_basis='model_analysis'`. Later hours become `record_kind='forecast'`, `measurement_basis='model_forecast'`, `issued_at=fetched_at`. Open-Meteo does not supply station observations; the API, README and frontend contract MUST say so. Never label this data 'official' or 'station'.
- Parallel arrays are zipped by index; length mismatches fail that location; `null` entries stay `NULL`.
- `source.attribution_text` and `license_url` come from verified provider terms and are returned with every record.
- Retry policy (`tenacity`): retry on timeouts, connection errors, `429` (respecting `Retry-After`) and `5xx`; no retry on other `4xx`; exponential backoff with jitter; max 3 attempts; a total wall-clock cap per run. Timeouts from Section 5.
- A forecast row for hour H is later superseded in practice by an observation row for hour H (different `record_kind`, so no conflict). Old forecast rows stay available for forecast-vs-actual analysis.
- MAY: `current` block ingestion (15-minute resolution) and a `backfill` CLI using the provider's historical endpoint.

### 8.3 RSS/Atom adapter (Phase 6)

- One `data_sources` row per feed with `config = {feed_url, category}`. Fetch bytes through the guarded HTTP client, then `feedparser.parse(bytes)`. Never pass a URL to feedparser.
- If the feed is malformed and yields no entries, the run is `failed`; if entries parse despite warnings, continue and record a warning.
- Normalization: sanitize title and summary with nh3 (all tags stripped), collapse whitespace, truncate; accept only `http`/`https` item URLs up to 2048 characters; `published_at` from `published_parsed` or `updated_parsed` converted to UTC, else `NULL` (do not substitute fetch time); cap at 200 entries per fetch.
- Dedup by `dedupe_key`; unchanged items are `skipped`, changed content hash is `updated`.
- News is stored only in `news_items`. It is never turned into weather records, never marked verified, and `is_official` comes from the source trust level only.
- Do not invent feed URLs. Find at least one real weather-related feed, confirm it is reachable and that its terms allow use, and add it as a **disabled** source; otherwise document the adapter as `UNVERIFIED` and ship only the test fixtures.

### 8.4 data.gov.in adapter (Phase 6)

- Verify the current API format, authentication (API key), pagination, rate limits and terms. Read the key from `DATA_GOV_IN_API_KEY`; without it `is_configured()` is false and the source cannot be enabled or run.
- Config per source: `resource_id`, `field_map` (provider field to canonical field), `unit_conversions`, `location_match` (match provider station or district names to configured location slugs), `max_pages`. Unmatched rows are `skipped` with a counter, not guessed.
- If a dataset's schema fits `weather_records` (and documentation supports it), map to `record_kind='observation'`; set `measurement_basis='station'` only if documentation says so, else `unknown`. `trust_level='official'` is assigned only in the seed or a migration after verification, never via the API.
- If a candidate dataset does not fit the schema (monthly aggregates, different dimensions), do **not** force it. Describe it in the Phase 6 report and propose a separate table.
- Never fabricate resource IDs or sample official data. If access cannot be verified, leave the adapter disabled and documented as `UNVERIFIED`.

### 8.5 Scheduler and worker (Phase 7)

`python -m app.worker` is a separate process:

- On start, mark `running` rows older than `INGESTION_RUN_TIMEOUT_SECONDS` as `abandoned`.
- Scheduled jobs exist only when `INGESTION_ENABLED=true` **and** the source has `is_enabled=true` **and** `is_configured()` is true. Re-sync jobs from the database every 60 seconds so admin `PATCH` changes apply without a restart.
- APScheduler job settings: `max_instances=1`, `coalesce=True`, a misfire grace time, small random jitter.
- A scheduled tick inserts a `queued` run (the partial unique index silently prevents overlap; catch the integrity error and skip), then executes it through the same `execute_run(run_id)` code path as manual runs.
- A poller every 10 seconds claims `queued` runs with `SELECT ... FOR UPDATE SKIP LOCKED`, marks them `running` and executes them. Manual runs from the API are processed even when `INGESTION_ENABLED=false`, as long as the source is configured (so you can test safely). If no worker is running, runs stay `queued`; document this.
- Per-run deadline checked between targets. Exceptions in a job are caught and recorded so the scheduler never dies. Graceful shutdown on SIGINT/SIGTERM: finish the current target, then mark any unfinished run `abandoned` with a reason.

## 9. Analytics

All aggregation happens in PostgreSQL (`date_trunc`, `FILTER`, `percentile_cont`, `regr_slope`, `generate_series`). pandas/NumPy are used only for the anomaly computation on a bounded window. All times are UTC. Analytics default to `kind=observation`; observations and forecasts are never mixed in one aggregate. Rainfall aggregates use `SUM`, never `AVG` of rates. Wind direction is never averaged arithmetically.

**`GET /analytics/summary`** query `from`, `to` (default last 7 days), `location_id` (optional). Response:

- `period`.
- `weather`: record counts by kind, locations with data, `temperature_c {min, mean_of_location_means, max}`, `wind {mean_speed_kmh, max_gust_kmh}`.
- `reports`: `total` and `by_status`. Anonymous callers get only `verified`; `pending` and `rejected` appear for reviewer and admin tokens.
- `sources`: one entry per source with `name`, `display_name`, `source_type`, `trust_level`, `freshness` and `last_success_at`. Freshness is `fresh` (last success within 2 x interval), `stale`, `never` or `disabled`.
- `ingestion` (admin only, otherwise `null`): runs by status in the period, `success_rate`, and the last failure time. No error text.

**`GET /analytics/timeseries`** query: `metric` (`temperature_c`, `relative_humidity_pct`, `precipitation_mm`, `wind_speed_kmh`, `wind_gust_kmh`), `location_id` (required), `from`, `to` (required, max 366 days), `interval` (`hour`, `day`, `week`, `month`), `agg` (`avg`, `min`, `max`, `sum`, `count`; default `avg`, default `sum` for precipitation; `sum` is allowed only for precipitation), `kind`, `fill_gaps` (default false; true returns `null` values for empty buckets), `include_trend` (SHOULD). More than 2000 buckets returns `422`. Response: `{metric, unit, location, kind, interval, agg, buckets:[{start, value, sample_count}], sources:[...], trend?:{method:'ols', slope_per_day, r_squared, n}}`. `value` is `null` when a bucket has no samples.

**`GET /analytics/locations`** query `from`, `to` (default 7 days), `sort`. Per active location: `latest_observation_at`, temperature min/mean/max, `total_precipitation_mm`, wind mean and max gust, `record_count`, `coverage_pct` (hours with data divided by expected hours), `report_counts` (verified; all statuses for staff).

**`GET /analytics/events`** query `from`, `to`, `event_type`, `location_id`, `group_by` (one of `event_type`, `location`, `status`, `day`), `status` (staff only). Response `{group_by, items:[{key, count}], totals:{verified, pending?, rejected?}}`. Anonymous callers see only verified data.

**Anomalies (SHOULD, `GET /analytics/anomalies`)**: query `location_id`, `metric`, `from`, `to` (default last 7 days), `baseline_days` (default 30), `threshold` (default 3.5). Method: modified z-score `0.6745 * (x - median) / MAD` against the baseline window for the same location and metric (observations only, evaluation window excluded). Requires at least 168 baseline samples, else `insufficient_data`; `MAD == 0` is skipped with a note. Each item carries `valid_at`, `metric`, `value`, `baseline {median, mad, n, window_days}`, `score`, `direction`, `method`, `threshold`, a plain-language `explanation` (for example, 'Value is 4.1 robust deviations above the 30-day median of 29.8 C, n=720'), `is_official_warning: false`, `verification: 'unverified'`, and the fixed `disclaimer: 'Statistical flag only. Not an official warning.'` The API MUST NOT label an anomaly a warning, alert or emergency, and a test must assert the three fields above on every anomaly item.

**Correctness testing:** each endpoint is tested against a deterministic fixture dataset with expected values computed independently (by hand and with pandas in the test), including empty ranges, `NULL` measurements, bucket boundaries, `fill_gaps`, forecast/observation separation, role-dependent fields, and range or interval caps.

## 10. Testing and CI

**Setup.** `TEST_DATABASE_URL` points to a dedicated database whose name ends in `_test` (the suite aborts otherwise). A session fixture runs `alembic upgrade head` once (so migrations are exercised); tests isolate state with per-test transaction rollback, or table truncation for tests that need real commits (concurrency, triggers). No test uses the real network: an autouse fixture blocks outbound sockets except to the local database, and all provider traffic is mocked with respx or `httpx.MockTransport`. Real-provider smoke tests are marked `@pytest.mark.live`, excluded by default, and run only manually; report their results honestly.

**Mandatory test matrix**

| Area | Must test |
| --- | --- |
| Validation and normalization | Unit conversion, range rejection (never clamped), `NULL` handling, UTC parsing, naive timestamps rejected, length limits, `extra='forbid'` |
| Migrations | Upgrade from empty, downgrade then upgrade, autogenerate yields no diff, CHECK and unique constraints reject bad rows, append-only triggers block `UPDATE`, `DELETE`, `TRUNCATE` on `report_reviews` and `audit_events` |
| Deduplication | Re-running the same payload gives `inserted=0, updated=0`; changed value gives `updated`; overlapping runs blocked by the partial unique index; concurrent manual triggers produce exactly one run |
| Provider failures | Timeout then retry then failure; `429` with `Retry-After`; `5xx`; no retry on `4xx`; malformed JSON; array length mismatch; oversize response; partial failure yields `partial`; stored errors contain no API key, token or URL query string |
| Reports | Always `pending`; client `status` rejected; coordinate and length bounds; nearest-location assignment; tracking-token flow; public list excludes pending and rejected; non-public id returns `404`; private fields never in public JSON |
| Review workflow | Every transition pair (allowed and denied), role limits, notes required where specified, `stale_version`, two concurrent reviews (exactly one wins), review and audit rows written, history immutable, reviewer identity recorded |
| Authentication | Uniform failure message and no user enumeration, lockout and reset, expired token, tampered token, wrong `alg` and `none`, wrong issuer or audience, `token_version` revocation, inactive user |
| Authorization | Role matrix from Section 6.2; an **automated test that enumerates every route in the OpenAPI schema** and asserts `/admin/*` routes return `401` without a token and `403` for the wrong role, so new routes cannot be forgotten |
| SSRF | IP literals, private/loopback/link-local/metadata ranges (IPv4 and IPv6), non-allow-listed host, redirect to a private address, simulated DNS rebinding, non-https, oversize body |
| Rate limiting | Sixth login within a minute returns `429` with `Retry-After`; report-submission limit; limits disabled only in the test environment flag |
| Pagination and filtering | Limit caps, offset, accurate `total`, deterministic order, invalid parameters give `422`, date-range caps |
| Analytics | Fixture-based correctness (Section 9), role-dependent output, anomaly flags and disclaimer fields |
| Privacy and security | Log redaction (token and password never appear in captured logs), no stack trace in errors, CORS allowed vs blocked origin, security headers, forbidden-keys check on every public schema |
| Health | `/health/ready` returns `503` when the database is unreachable, with no error text |

**Coverage.** At least 80% line and branch coverage on `services`, `repositories`, `ingestion`, `analytics` and `core`, and at least 90% on `core/security.py`, authorization dependencies and the SSRF guard. CI fails below these thresholds.

**GitHub Actions** (`.github/workflows/backend-ci.yml`): trigger on push and pull request for `backend/**`; `permissions: contents: read`; Python 3.12 with pip caching; a PostgreSQL 16 service container (CI infrastructure only; the project itself still needs no Docker) or an apt-installed PostgreSQL; steps: install `requirements-dev.txt`, `ruff check`, `ruff format --check`, `alembic upgrade head`, `pytest --cov` with thresholds, upload the coverage report. Test secrets are throwaway values defined in the workflow only. Use current major versions of official actions (verify at implementation time). You cannot see CI results unless the branch is pushed; state honestly whether a CI run actually happened.

## 11. Local Execution and Deployment

The README MUST contain exact commands, and you MUST execute them from a clean virtual environment and an empty database before reporting that they work. If any step could not be executed, say so in the report.

```
cd backend
python3.12 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
cp .env.example .env               # then edit values
psql -U postgres -c 'CREATE DATABASE weather_dev;'
psql -U postgres -c 'CREATE DATABASE weather_test;'
alembic upgrade head
python -m app.cli seed-sources
python -m app.cli seed-locations --file config/locations.yaml
python -m app.cli create-admin --email you@example.com
uvicorn app.main:app --reload --port 8000     # API docs at http://localhost:8000/docs
python -m app.worker                          # second terminal: ingestion worker
ruff check . && ruff format --check . && pytest --cov=app
```

The README also documents PostgreSQL installation for Windows (official installer), macOS (Homebrew) and Ubuntu (apt), creating a dedicated database role, setting `DATABASE_URL`, how to enable ingestion (set `INGESTION_ENABLED=true`, verify each source, enable via the admin API), common errors, and how the frontend connects (CORS origin and base URL).

**Deployment (Phase 8).** Recommended: Render with a web service, a background worker and a managed PostgreSQL instance (Railway is an acceptable alternative). Verify current plan limits and pricing before recommending a tier.

- Build: `pip install -r requirements.txt`. Pre-deploy or release step: `alembic upgrade head`. Web start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers`, with `TRUSTED_PROXY_IPS` configured to the platform's proxy range. Worker start: `python -m app.worker`.
- HTTPS is terminated by the platform; the API enforces HTTPS-only CORS origins in production and sets no cookies.
- Production environment variables are set in the provider dashboard, never in the repository. Generate `JWT_SECRET` and `IP_HASH_SECRET` with a CSPRNG (for example `python -c 'import secrets; print(secrets.token_urlsafe(48))'`). Rotating `JWT_SECRET` logs everyone out; document that.
- `CORS_ORIGINS` is the production frontend URL only. Consider `API_DOCS_ENABLED=false` or restricting docs in production.
- Backups: enable the provider's automated backups (and point-in-time recovery if the plan supports it), document a manual `pg_dump` command, and perform and document one test restore.
- Migrations are backward compatible (expand, then contract) so a rollback of application code stays safe.
- Use `/health/ready` as the platform health check and ship logs to the platform's log viewer. Document cold-start behavior if the plan sleeps idle services.
- Production checklist in `docs/deployment.md`: secrets set, admin created, sources reviewed, ingestion enabled deliberately, CORS correct, docs setting chosen, backups verified.
