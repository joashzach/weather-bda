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
git clone -b frontend/monsoon-dashboard https://github.com/joashzach/weather-bda.git
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

Run syntax checks with `npm.cmd run check`.

The frontend runs with **demo data** by default; no backend is required. API configuration lives in `dist/config.js`. This branch contains frontend work only, not the backend or machine-learning services.

On macOS/Linux, install Node.js and Git using your platform's installers and use `npm` instead of `npm.cmd`.
