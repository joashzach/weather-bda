# External Weather & Data Provider Specifications and Notes

This document records the official documentation, access dates, parameters, rate limits, license terms, and schema compatibility for all external providers used by the Weather Big Data Analytics platform in compliance with Rule 5.

---

## 1. Open-Meteo Weather Forecast API

- **Official Documentation URL:** https://open-meteo.com/en/docs
- **Access / Verification Date:** 2026-10-20
- **Verification Status:** `VERIFIED`
- **Trust Level:** `provider_model` (Model-derived reanalysis and forecasts; NEVER station observations, NEVER official data)
- **Adapter Key:** `open_meteo`

### 1.1 Licensing and Attribution Terms
- **License:** Creative Commons Attribution 4.0 International (CC BY 4.0).
- **Commercial / Non-Commercial Terms:** Free for non-commercial use up to 10,000 daily API requests. Commercial use or higher volume requires an API key and commercial subscription.
- **Attribution Text:** "Weather data by Open-Meteo.com under CC BY 4.0"
- **License URL:** https://creativecommons.org/licenses/by/4.0/
- **Homepage URL:** https://open-meteo.com/
- **Attribution Policy:** Displayed alongside all weather data returned to frontend and public consumers. Must never be labeled "official" or "station reading".

### 1.2 Rate Limits (Free Tier)
- **Per Minute:** 600 calls
- **Per Hour:** 5,000 calls
- **Per Day:** 10,000 calls
- **Concurrency:** Maximum 10 concurrent requests

### 1.3 Endpoint & Parameters
- **Base Endpoint:** `https://api.open-meteo.com/v1/forecast`
- **HTTP Method:** `GET`
- **Request Parameters:**
  - `latitude`: Float between -90.0 and 90.0 (required)
  - `longitude`: Float between -180.0 and 180.0 (required)
  - `hourly`: Comma-separated list of hourly variables:
    - `temperature_2m` (Air temperature at 2 meters)
    - `apparent_temperature` (Perceived temperature)
    - `relative_humidity_2m` (Relative humidity at 2 meters)
    - `precipitation` (Total precipitation: rain, showers, snow)
    - `rain` (Rain amount)
    - `precipitation_probability` (Precipitation probability, 0-100%)
    - `wind_speed_10m` (Wind speed at 10 meters)
    - `wind_gusts_10m` (Maximum gusts at 10 meters)
    - `wind_direction_10m` (Wind direction in degrees, 0-360°)
  - `temperature_unit`: `celsius` (explicitly requested)
  - `wind_speed_unit`: `kmh` (explicitly requested)
  - `precipitation_unit`: `mm` (explicitly requested)
  - `timezone`: `UTC` (explicitly requested)
  - `timeformat`: `iso8601` (returns timestamps in ISO 8601 UTC)
  - `past_days`: Integer 0..92 (default 2 for past model analysis)
  - `forecast_days`: Integer 1..16 (default 7 for model forecasts)

### 1.4 Observation vs Forecast Split Rules
Open-Meteo returns parallel arrays of hourly predictions covering past days and future forecast days.
- **Observation Split:** Hourly records where `valid_at <= floor_to_hour(fetched_at)` are categorized as:
  - `record_kind = 'observation'`
  - `measurement_basis = 'model_analysis'`
  - `issued_at = NULL`
- **Forecast Split:** Hourly records where `valid_at > floor_to_hour(fetched_at)` are categorized as:
  - `record_kind = 'forecast'`
  - `measurement_basis = 'model_forecast'`
  - `issued_at = fetched_at`

### 1.5 Error Handling & Retry Policies
- Tenacity retry on connection errors, timeouts, HTTP 429 (respecting `Retry-After`), and HTTP 5xx.
- No retry on client 4xx errors (e.g. 400 Bad Request).
- Maximum 3 attempts with exponential backoff and jitter.
