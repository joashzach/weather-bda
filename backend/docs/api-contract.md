# Weather Big Data Analytics - Backend API Contract & OpenAPI Specification

**Contract Specification Document & Parity Verification**  
**Version:** 1.0.0  
**Base URL:** `/api/v1` (Production: `https://api.yourdomain.com/api/v1`, Local Dev: `http://localhost:8000/api/v1`)  
**OpenAPI JSON:** `http://localhost:8000/openapi.json`  
**Swagger UI:** `http://localhost:8000/docs`  
**Redoc:** `http://localhost:8000/redoc`

---

## 1. Architectural Standards & Envelopes

### 1.1 HTTP Status Codes & Error Envelopes
All API errors return a uniform, machine-readable JSON envelope:

```json
{
  "error": {
    "code": "resource_not_found",
    "message": "The requested resource could not be found.",
    "details": null,
    "request_id": "018f3a5b-9d41-710e-9087-ef82c5a11c82"
  }
}
```

#### Standard Error Codes:
| HTTP Status | Error Code | Description |
|---|---|---|
| `400 Bad Request` | `invalid_request` / `malformed_body` | Syntactic validation failure or invalid payload format |
| `401 Unauthorized` | `not_authenticated` / `token_expired` | Missing or invalid Bearer token |
| `403 Forbidden` | `permission_denied` | Insufficient RBAC role permissions |
| `404 Not Found` | `resource_not_found` / `location_not_found` | Target resource does not exist |
| `409 Conflict` | `conflict` / `already_running` / `stale_version` | Optimistic lock collision or concurrent duplicate run |
| `422 Unprocessable` | `validation_error` / `ssrf_violation` | Semantic validation error (Pydantic field failure, SSRF restriction) |
| `429 Too Many Requests` | `rate_limit_exceeded` | Client exceeded endpoint rate limit quota |
| `500 Internal Error` | `internal_server_error` | Unhandled server exception with sanitized message |

### 1.2 Global Request & Response Headers
- `Authorization: Bearer <access_token>`: Provided on authenticated requests.
- `X-Request-ID`: Client request tracking UUID returned on every HTTP response.
- `Retry-After`: Returned on HTTP `429 Too Many Requests` responses with integer seconds to backoff.
- `Content-Type: application/json`: Used for all JSON request and response payloads.
- `X-Tracking-Token`: Secret single-use UUID returned upon citizen report submission to allow anonymous submitters to track report status.

### 1.3 Standard Pagination Envelope
Paginated collection endpoints follow this standard pagination structure:

```json
{
  "items": [],
  "total": 128,
  "limit": 50,
  "offset": 0
}
```

- `limit`: Number of items requested per page (default: 50, maximum: 200 or 500 depending on endpoint).
- `offset`: Number of items skipped from the start of the query (default: 0).
- `total`: Total count of matching records across all pages.

---

## 2. Authentication & Authorization (RBAC)

The system enforces three user access levels:
1. **Anonymous / Public**: Unauthenticated caller. Can read weather data, view verified citizen reports, view public news, and submit citizen reports.
2. **Reviewer (Staff)**: Authenticated user with role `reviewer` or `admin`. Can access moderation queues, review/verify/reject/reopen citizen reports, and view private report metadata.
3. **Admin (Staff)**: Authenticated user with role `admin`. Full access including data source configuration, manual ingestion triggers, ingestion run inspection, and audit logs.

### 2.1 `POST /auth/register`
- **Access**: Public
- **Request Body**:
  ```json
  {
    "email": "user@example.com",
    "password": "StrongPassword123!",
    "display_name": "Jane Doe"
  }
  ```
- **Response `201 Created`**:
  ```json
  {
    "user": {
      "id": "c1f7a0b2-...",
      "email": "user@example.com",
      "display_name": "Jane Doe",
      "role": "reviewer",
      "created_at": "2026-10-21T00:00:00Z"
    },
    "token": {
      "access_token": "eyJhbGciOi...",
      "refresh_token": "eyJhbGciOi...",
      "token_type": "bearer",
      "expires_in": 1800
    }
  }
  ```

### 2.2 `POST /auth/login`
- **Access**: Public (Subject to lockout: 5 failed attempts in 15 minutes)
- **Request Body**:
  ```json
  {
    "email": "user@example.com",
    "password": "StrongPassword123!"
  }
  ```
- **Response `200 OK`**: Returns `{ "user": UserProfile, "token": AuthToken }`.

### 2.3 `POST /auth/refresh`
- **Access**: Public
- **Request Body**:
  ```json
  {
    "refresh_token": "eyJhbGciOi..."
  }
  ```
- **Response `200 OK`**: Returns refreshed `{ "token": AuthToken }`.

### 2.4 `GET /auth/me`
- **Access**: Authenticated (`reviewer` or `admin`)
- **Headers**: `Authorization: Bearer <token>`
- **Response `200 OK`**: Returns current `UserProfile`.

### 2.5 `POST /auth/logout`
- **Access**: Authenticated
- **Headers**: `Authorization: Bearer <token>`
- **Response `200 OK`**: `{ "detail": "Logged out" }` (Increments `token_version` to invalidate all active JWTs).

---

## 3. Public Core Data Endpoints

### 3.1 `GET /locations`
- **Access**: Public
- **Summary**: List all active geographic data collection points.
- **Response `200 OK`**:
  ```json
  {
    "items": [
      {
        "id": 1,
        "slug": "bangalore",
        "name": "Bengaluru",
        "region": "Karnataka",
        "country_code": "IN",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "is_active": true
      }
    ]
  }
  ```

### 3.2 `GET /weather`
- **Access**: Public
- **Query Parameters**:
  - `location_id` (int, optional): Filter by location.
  - `kind` (string, default: `observation`): `observation`, `forecast`, or `all`.
  - `source` (string, optional): Data source identifier (e.g., `open_meteo`).
  - `from` (ISO 8601 UTC, optional): Inclusive lower bound for `valid_at`.
  - `to` (ISO 8601 UTC, optional): Exclusive upper bound for `valid_at`.
  - `sort` (string, default: `-valid_at`): `-valid_at` or `valid_at`.
  - `limit` (int, default: 50, max: 500): Pagination limit.
  - `offset` (int, default: 0): Pagination offset.
- **Response `200 OK`**:
  ```json
  {
    "items": [
      {
        "id": 101,
        "location_id": 1,
        "source_id": 1,
        "kind": "observation",
        "valid_at": "2026-10-21T00:00:00Z",
        "temperature_c": 24.5,
        "apparent_temperature_c": 25.1,
        "relative_humidity_pct": 78,
        "precipitation_mm": 0.0,
        "rain_mm": 0.0,
        "precipitation_probability_pct": 10,
        "wind_speed_kmh": 12.4,
        "wind_gust_kmh": 22.1,
        "wind_direction_deg": 180,
        "weather_code": 1,
        "weather_code_meaning": "Mainly clear",
        "created_at": "2026-10-21T00:05:00Z"
      }
    ],
    "total": 1,
    "limit": 50,
    "offset": 0
  }
  ```

### 3.3 `GET /weather/latest`
- **Access**: Public
- **Query Parameters**: `location_id` (optional), `kind` (default: `observation`).
- **Response `200 OK`**: `{ "items": WeatherRecordPublic[] }` returning the newest observation or earliest upcoming forecast for each active location.

### 3.4 `GET /weather/{id}`
- **Access**: Public
- **Path Parameter**: `id` (integer)
- **Response `200 OK`**: Returns single `WeatherRecordPublic` or `404 resource_not_found`.

### 3.5 `GET /news`
- **Access**: Public
- **Query Parameters**: `source` (optional), `category` (optional), `from` (optional), `to` (optional), `limit` (default: 50), `offset` (default: 0).
- **Response `200 OK`**: Paginated list of sanitized news and meteorological advisories.

---

## 4. Citizen Reports Flow

### 4.1 `POST /reports`
- **Access**: Public (Subject to IP rate limiting: 5 submissions per hour)
- **Request Body**:
  ```json
  {
    "latitude": 12.9716,
    "longitude": 77.5946,
    "event_time": "2026-10-21T00:15:00Z",
    "event_type": "heavy_rain",
    "severity": "high",
    "description": "Flash flooding on MG road underpass.",
    "evidence_type": "link",
    "evidence_url": "https://example.com/photo.jpg"
  }
  ```
- **Response `201 Created`**:
  ```json
  {
    "id": "e2b5e28a-...",
    "status": "pending",
    "tracking_token": "a1b2c3d4-...",
    "message": "Report submitted successfully. Retain your tracking token to view review status."
  }
  ```

### 4.2 `GET /reports`
- **Access**: Public (Verified reports only for anonymous callers; all statuses for staff).
- **Query Parameters**: `status`, `event_type`, `location_id`, `from`, `to`, `sort`, `limit`, `offset`.
- **Response `200 OK`**: Paginated list of `CitizenReportPublic` (or `CitizenReportStaff` if authenticated).

### 4.3 `GET /reports/{id}`
- **Access**: Public for verified reports. Pending/rejected reports require reviewer authentication or `X-Tracking-Token` header.
- **Response `200 OK`**: Returns report details. Sensitive fields (`client_ip_hash`, `raw_payload`, internal reviewer notes) omitted for unauthenticated callers.

---

## 5. Analytics Dashboard Endpoints

### 5.1 `GET /analytics/summary`
- **Access**: Public (Staff callers receive additional ingestion queue telemetry).
- **Query Parameters**: `from` (optional), `to` (optional), `location_id` (optional).
- **Response `200 OK`**:
  ```json
  {
    "period": { "from": "2026-10-14T00:00:00Z", "to": "2026-10-21T00:00:00Z" },
    "weather": {
      "record_counts": { "observation": 168, "forecast": 168 },
      "records_by_kind": { "observation": 168, "forecast": 168 },
      "locations_with_data": 3,
      "temperature_c": { "min": 18.2, "mean_of_location_means": 25.4, "max": 33.1 },
      "wind": { "mean_speed_kmh": 14.2, "max_gust_kmh": 36.8 }
    },
    "reports": {
      "total": 12,
      "by_status": { "verified": 8, "pending": 3, "rejected": 1 }
    },
    "sources": [
      {
        "name": "open_meteo",
        "display_name": "Open-Meteo Weather API",
        "source_type": "weather_api",
        "trust_level": "provider_model",
        "freshness": "fresh",
        "last_success_at": "2026-10-21T00:30:00Z"
      }
    ],
    "ingestion": {
      "runs_by_status": { "succeeded": 24, "failed": 0 },
      "success_rate": 1.0,
      "last_failure_at": null
    }
  }
  ```

### 5.2 `GET /analytics/timeseries`
- **Access**: Public
- **Query Parameters**: `metric`, `interval` (`hour`, `day`, `week`, `month`), `agg` (`avg`, `min`, `max`, `sum`, `count`), `location_id`, `from`, `to`.

### 5.3 `GET /analytics/locations`
- **Access**: Public
- **Query Parameters**: `metric`, `from`, `to`, `sort` (`name`, `-name`, `record_count`, `-record_count`, `coverage_pct`, `-coverage_pct`).

### 5.4 `GET /analytics/events`
- **Access**: Public
- **Query Parameters**: `from`, `to`, `group_by` (`event_type`, `location`, `status`, `day`).

### 5.5 `GET /analytics/anomalies`
- **Access**: Public
- **Query Parameters**: `metric`, `window_hours` (default: 72), `threshold_std` (default: 3.0).

---

## 6. Admin & Moderation Endpoints

### 6.1 `GET /admin/reports/pending`
- **Access**: Staff (`reviewer` or `admin`)
- **Query Parameters**: `limit`, `offset`, `sort`, `event_type`, `location_id`, `from`, `to`.
- **Response `200 OK`**: Oldest-first moderation queue with optimistic `row_version`.

### 6.2 `POST /admin/reports/{id}/review`
- **Access**: Staff (`reviewer` or `admin`)
- **Request Body**:
  ```json
  {
    "decision": "verify",
    "note": "Verified against local radar confirmation.",
    "row_version": 1
  }
  ```
- **Decisions**: `verify`, `reject`, `reopen`.
- **Concurrency**: Returns `409 Conflict` (`stale_version`) if `row_version` does not match current database state.

### 6.3 `GET /admin/reports/{id}/reviews`
- **Access**: Staff (`reviewer` or `admin`)
- **Response `200 OK`**: Immutable chronological audit trail of all moderation actions on the report.

### 6.4 `GET /admin/sources`
- **Access**: Admin only
- **Response `200 OK`**:
  ```json
  {
    "items": [
      {
        "id": 1,
        "name": "open_meteo",
        "display_name": "Open-Meteo Weather API",
        "source_type": "weather_api",
        "adapter_key": "open_meteo",
        "trust_level": "provider_model",
        "is_enabled": true,
        "interval_seconds": 3600,
        "configured": true,
        "freshness": "fresh",
        "attribution_text": "Weather data by Open-Meteo.com",
        "license_url": "https://open-meteo.com/en/terms",
        "homepage_url": "https://open-meteo.com",
        "last_attempt_at": "2026-10-21T00:30:00Z",
        "last_success_at": "2026-10-21T00:30:00Z",
        "config": { "past_days": 2, "forecast_days": 7 },
        "last_run": {
          "id": 10,
          "status": "succeeded",
          "trigger": "scheduled",
          "queued_at": "2026-10-21T00:30:00Z",
          "records_fetched": 48,
          "inserted": 0,
          "updated": 0,
          "skipped": 48,
          "failed": 0
        }
      }
    ]
  }
  ```

### 6.5 `PATCH /admin/sources/{id}`
- **Access**: Admin only
- **Request Body**:
  ```json
  {
    "is_enabled": true,
    "interval_seconds": 7200,
    "display_name": "Open-Meteo Hourly Feed"
  }
  ```
- **Validation**: Enforces SSRF checks on any candidate URLs in `config`.

### 6.6 `POST /admin/ingestion/{source}/run`
- **Access**: Admin only
- **Path Parameter**: `source` (string, e.g. `open_meteo`)
- **Response `202 Accepted`**: `{ "run_id": 11, "status": "queued" }`.
- **Conflicts**: Returns `409 already_running` if a run is already queued/running; `409 source_not_configured` if required config is missing; `404 source_not_found` if unknown.

### 6.7 `GET /admin/ingestion/runs`
- **Access**: Admin only
- **Query Parameters**: `source`, `status`, `from`, `to`, `limit` (default: 50), `offset` (default: 0).
- **Response `200 OK`**: Paginated list of ingestion runs.

### 6.8 `GET /admin/ingestion/runs/{id}`
- **Access**: Admin only
- **Path Parameter**: `id` (integer)
- **Response `200 OK`**: Detailed run statistics with sanitized errors and target execution metadata.
