# Weather Analytics Frontend Integration Guide

**Integration & Developer Handover Documentation**  
**Audience:** React / Vite / TypeScript Frontend Engineering Team  
**Backend Base URL:** `http://localhost:8000/api/v1`  
**OpenAPI Spec Endpoint:** `http://localhost:8000/openapi.json`

---

## 1. Local Development & Networking

### 1.1 Vite Dev Server Configuration
The frontend dev server runs at `http://localhost:5173`. The backend is preconfigured to permit CORS requests originating from this address via `CORS_ORIGINS=http://localhost:5173`.

Alternatively, configure a reverse proxy in `vite.config.ts` to avoid cross-origin handling during local development:

```typescript
// vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/openapi.json': {
        target: 'http://localhost:8000',
      },
    },
  },
});
```

### 1.2 TypeScript Contract Generation
Generate strong TypeScript types directly from the backend's live OpenAPI schema:

```bash
npx openapi-typescript http://localhost:8000/openapi.json -o src/types/api-schema.d.ts
```

---

## 2. HTTP Client & Auth Interceptor Architecture

### 2.1 Axios Instance Setup with Bearer Token & Request Tracing

```typescript
// src/api/client.ts
import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor: attach Bearer token
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem('access_token');
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor: handle 401 token expiry and error unpacking
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<{ error: { code: string; message: string; request_id: string } }>) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    // Automatic token refresh on 401
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      const refreshToken = localStorage.getItem('refresh_token');

      if (refreshToken) {
        try {
          const res = await axios.post('/api/v1/auth/refresh', { refresh_token: refreshToken });
          const newAccessToken = res.data.token.access_token;
          localStorage.setItem('access_token', newAccessToken);

          if (originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
          }
          return api(originalRequest);
        } catch {
          // Refresh failed - force logout
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          window.location.href = '/login?session_expired=1';
        }
      }
    }

    return Promise.reject(error);
  }
);

export default api;
```

---

## 3. Core Feature Workflows

### 3.1 Authentication & RBAC Route Guarding
Store user profile in React Context / Zustand.

```typescript
export interface UserProfile {
  id: string;
  email: string;
  display_name: string;
  role: 'admin' | 'reviewer';
  created_at: string;
}
```

- **Anonymous**: Access to `/` (Map), `/analytics` (Summary), `/reports/new` (Submission), `/news` (Advisories).
- **Reviewer**: Access to `/admin/moderation` (Queue, Verify/Reject transitions).
- **Admin**: Access to `/admin/sources` (Source toggles, intervals) and `/admin/ingestion` (Manual run triggers, telemetry).

### 3.2 Citizen Report Submission Flow
1. User marks geolocation on the map (`latitude`, `longitude`).
2. User submits description, event type, severity, and optional evidence link.
3. Backend automatically identifies the nearest weather collection location and hashes client IP for privacy.
4. Response returns:
   - `id`: Unique report UUID.
   - `tracking_token`: Single-use tracking secret.
   - Store `tracking_token` in `localStorage` under `submitted_reports`:
     ```typescript
     const reportHistory = JSON.parse(localStorage.getItem('my_reports') || '[]');
     reportHistory.push({ id: res.data.id, token: res.data.tracking_token });
     localStorage.setItem('my_reports', JSON.stringify(reportHistory));
     ```
5. When querying `GET /reports/{id}` for a pending report submitted by the user, pass `X-Tracking-Token: <token>`.

### 3.3 Moderation Queue & Optimistic Concurrency
When reviewing a pending report:
1. `GET /admin/reports/pending` returns items with a `row_version: number` (starts at 1).
2. When the moderator submits a decision (`verify`, `reject`, `reopen`):
   ```typescript
   await api.post(`/admin/reports/${reportId}/review`, {
     decision: 'verify',
     note: 'Verified against local weather radar and satellite images.',
     row_version: report.row_version,
   });
   ```
3. If another moderator reviewed the report simultaneously, the backend returns `409 Conflict` with code `stale_version`. The frontend should display: *"This report was already updated by another moderator. Refreshing queue..."* and reload the queue.

### 3.4 Data Source Trust Badges
Present clear visual trust indicators across weather cards and charts:

| Trust Level | Label | Badge Color / Style | Notes |
|---|---|---|---|
| `official` | Official IMD | Deep Navy / Blue (`#1E40AF`) | Government meteorological department |
| `provider_model` | Provider Model | Cyan / Teal (`#0D9488`) | Numerical forecast API (Open-Meteo) |
| `news` | Media Advisory | Amber (`#D97706`) | RSS / Atom news feeds |
| `citizen` | Citizen Report | Emerald (`#059669`) | Verified crowd observations |

### 3.5 Manual Ingestion Runs & Telemetry
In the Admin Dashboard:
1. Trigger ingestion: `POST /admin/ingestion/{source}/run`.
2. Response returns `202 Accepted` with `{ "run_id": 12, "status": "queued" }`.
3. Poll `GET /admin/ingestion/runs/{run_id}` every 2 seconds until status changes to `succeeded` or `failed`.
4. Display deduplication counts in telemetry widget:
   - `records_fetched`: Total items fetched from provider.
   - `inserted`: New records added.
   - `updated`: Existing records refreshed.
   - `skipped`: Unchanged duplicates omitted.
   - `failed`: Failed target items with sanitized error summary.
