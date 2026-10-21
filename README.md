# Monsoon — Weather Dashboard

Frontend for exploring weather reports, filtering events, viewing analytics, and reviewing verification status. Includes an interactive map, animated particle intro, and dark/light themes.

## 1. Install Node.js and Git (Windows)

Open PowerShell and paste:

```powershell
winget install --id OpenJS.NodeJS.LTS -e --source winget
winget install --id Git.Git -e --source winget
```

Approve the installer prompts, then **close and reopen PowerShell**.

## 2. Download and run

```powershell
git clone -b codex/frontend-update-20261021 https://github.com/joashzach/weather-bda.git
cd weather-bda
npm.cmd ci
npm.cmd run dev
```

Open **http://127.0.0.1:5173** in your browser.

Keep PowerShell open while using the site. Press **Ctrl+C** to stop it.

## Run it again later

Open PowerShell in the downloaded `weather-bda` folder and run:

```powershell
npm.cmd run dev
```

## Get updates

Stop the server first, then run these commands inside `weather-bda`:

```powershell
git pull --ff-only
npm.cmd ci
npm.cmd run dev
```

## Development

The runnable frontend is included in `dist/`. If you change the React animation source in `src/`, rebuild it:

```powershell
npm.cmd run build
```

Run syntax checks with `npm.cmd run check` and lint with `npm.cmd run lint`.

The frontend uses the backend API; demo mode is disabled. Set the backend origin in `dist/config.js` (default: **http://localhost:8000**) and allow the frontend origin (**http://127.0.0.1:5173**) in backend CORS settings. A compatible running backend is required for weather data, reports, authentication, and administration features. This branch contains frontend work only.

On macOS/Linux, install Node.js and Git using your platform's installers and use `npm` instead of `npm.cmd`.
