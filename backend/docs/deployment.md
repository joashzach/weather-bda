# Weather Big Data Analytics - Production Deployment Guide

**Target Environment:** Render Cloud Platform + Managed PostgreSQL 16  
**Security Standard:** Strict PRD Security Hardening & Zero-Knowledge Secret Management

---

## 1. Architecture & Services Layout

The production deployment consists of three decoupled components:

```mermaid
graph TD
    Client[Browser / React Frontend] -->|HTTPS| RenderWeb[Render Web Service: FastAPI API]
    RenderWeb -->|SSL| Postgres[(Render Managed Postgres 16)]
    RenderWorker[Render Background Worker: Worker Process] -->|SSL| Postgres
    RenderWorker -->|SSRF-Guarded Outbound HTTPS| ExternalAPIs[Open-Meteo / IMD / data.gov.in]
```

1. **Web Service (API Server)**:
   - **Type**: Web Service (Python 3.12)
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 4`
   - **Health Check Path**: `/api/v1/health`
2. **Background Worker (Ingestion Engine)**:
   - **Type**: Background Worker
   - **Start Command**: `python -m app.worker`
   - **Scaling**: 1 replica (Prevents scheduler duplication; `SELECT ... FOR UPDATE SKIP LOCKED` guarantees concurrency safety if scaled)
3. **Managed PostgreSQL**:
   - **Version**: PostgreSQL 16
   - **Storage**: SSD with automatic point-in-time recovery and automated daily backups

---

## 2. Generating Cryptographically Secure Secrets

All production secrets **must** be generated using Python's CSPRNG (`secrets` module) or `/dev/urandom`. **Never reuse development secrets or placeholder strings.**

Run the following command locally to generate production secrets:

```bash
python -c "import secrets; print('JWT_SECRET=' + secrets.token_hex(32)); print('IP_HASH_SECRET=' + secrets.token_hex(24))"
```

---

## 3. Production Environment Variables Reference

Configure these environment variables in the Render Dashboard under **Environment**:

| Variable | Recommended Production Value | Description |
|---|---|---|
| `ENVIRONMENT` | `production` | Enables strict SSL and production exception handling |
| `DATABASE_URL` | `postgresql+psycopg://user:pass@host:5432/dbname?sslmode=require` | Managed Postgres connection string |
| `JWT_SECRET` | *(64-hex char random string)* | Cryptographic key for signing JWT auth tokens |
| `JWT_ISSUER` | `weather-bda` | JWT issuer claim |
| `JWT_AUDIENCE` | `weather-bda-api` | JWT audience claim |
| `ACCESS_TOKEN_TTL_MINUTES` | `30` | Access token lifespan in minutes |
| `IP_HASH_SECRET` | *(48-hex char random string)* | Cryptographic HMAC salt for anonymizing client IPs |
| `CORS_ORIGINS` | `https://your-frontend.onrender.com` | Strict comma-separated list of allowed origins (no wildcards) |
| `API_DOCS_ENABLED` | `false` | Disables Swagger UI (`/docs`) and OpenAPI spec in production |
| `INGESTION_ENABLED` | `true` | Enables scheduled periodic worker ingestion runs |
| `ALLOWED_SOURCE_HOSTS` | `api.open-meteo.com,api.data.gov.in,mausam.imd.gov.in` | Strict whitelist of outbound hostnames for SSRF guard |
| `HTTP_CONNECT_TIMEOUT` | `5.0` | Socket connect timeout in seconds |
| `HTTP_READ_TIMEOUT` | `15.0` | Socket read timeout in seconds |
| `HTTP_MAX_RESPONSE_BYTES` | `5242880` | Maximum response size cap (5MB) |
| `RATE_LIMIT_LOGIN` | `5/minute` | Rate limit for auth login endpoint |
| `RATE_LIMIT_REPORT_SUBMIT` | `5/hour` | Rate limit for citizen report submissions |
| `RATE_LIMIT_PUBLIC_READ` | `120/minute` | Rate limit for public read endpoints |

---

## 4. Pre-Deploy & Database Initialization Workflow

Render provides a **Pre-Deploy Command** step that runs before the web service traffic is switched.

### 4.1 Set the Pre-Deploy Command
```bash
alembic upgrade head
```

### 4.2 Initial One-Time Data Bootstrap
Once the database schema is migrated, execute the following commands via the Render SSH Shell or one-off Job:

```bash
# 1. Seed active geographic collection locations
python -m app.cli seed-locations

# 2. Seed default data sources (IMD, Open-Meteo, data.gov.in)
python -m app.cli seed-sources

# 3. Create initial Administrator account (prompts securely for password)
python -m app.cli create-admin --email admin@yourdomain.com --name "System Administrator"
```

---

## 5. Automated Backups & Disaster Recovery Test

### 5.1 Automated Backups
Render Managed Postgres provides automated daily backups with 7-day retention.

### 5.2 Manual Backup Procedure (pg_dump)
To take an ad-hoc snapshot before major operations:

```bash
pg_dump -Fc --no-acl --no-owner -d "$DATABASE_URL" -f "backup_$(date +%Y%m%d_%H%M%S).dump"
```

### 5.3 Disaster Recovery / Restore Procedure
To verify backup integrity or perform disaster recovery:

1. Create a fresh target test database:
   ```bash
   createdb -h localhost -U postgres weather_restore_test
   ```
2. Restore the custom-format dump into the target database:
   ```bash
   pg_restore -h localhost -U postgres -d weather_restore_test --clean --if-exists --no-acl --no-owner backup_20261021_000000.dump
   ```
3. Run schema and data verification queries:
   ```sql
   -- Verify all tables restored
   SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';

   -- Verify data counts
   SELECT count(*) FROM locations;
   SELECT count(*) FROM data_sources;
   SELECT count(*) FROM weather_records;
   SELECT count(*) FROM users;
   ```
4. Confirm Alembic version reflects current head:
   ```sql
   SELECT version_num FROM alembic_version;
   ```

---

## 6. Production Readiness Checklist

Before marking the deployment live:

- [x] **CSPRNG Secrets**: `JWT_SECRET` and `IP_HASH_SECRET` generated with $\ge 32$ bytes of entropy; neither matches development defaults.
- [x] **SSL / TLS**: All connections forced over HTTPS; Postgres URL enforces `sslmode=require`.
- [x] **CORS Lockdown**: `CORS_ORIGINS` points exclusively to the production frontend domain; wildcard `*` is strictly rejected by settings validator.
- [x] **SSRF Protection**: `ALLOWED_SOURCE_HOSTS` whitelist active; loopback, private RFC 1918, link-local, and AWS metadata IPs blocked.
- [x] **Rate Limiting**: SlowAPI rate limiting enabled on login (5/min), reports (5/hr), and public read (120/min).
- [x] **Account Lockout**: 5 failed login attempts triggers 15-minute account lockout.
- [x] **Documentation Hardening**: `API_DOCS_ENABLED=false` set in production environment to avoid exposing Swagger UI.
- [x] **Sanitized Errors**: No stack traces or raw database exceptions leak to callers; all errors wrapped in `{ error: { code, message, request_id } }`.
- [x] **Audit Trail**: All administrative and moderation state transitions recorded to immutable `audit_logs` table with HMAC-hashed IP.
- [x] **Clean Repository**: No `.env` files or credentials committed to Git.
