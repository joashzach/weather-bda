# Monsoon — weather intelligence frontend

A responsive weather analytics dashboard and admin review interface. This branch contains frontend work only.

## Run locally

Requires Node.js and npm.

~~~sh
npm ci
npm run build
npm run check
npm run dev
~~~

Open http://127.0.0.1:5173. The static server serves dist/; rebuild after changing React motion code in src/. Plain app/CSS files in dist/ are editable source.

## Features

- Date-period, location, event and verification filters
- Interactive map with toggleable locations, clear selection and stable scroll
- Event breakdown, analytics, report details and CSV export
- Admin review queue and browser-local demo decisions
- Dark-first charcoal/orange/amber design with a persistent light theme
- Scroll-driven particle scene, animated tabs, chart reveals and React Bits magnetic controls
- Reduced-motion support and responsive layouts

## Demo and API integration

Demo mode is enabled in dist/config.js. Reports, verification states and AI-related UI are sample data; no machine learning classifier or ingestion backend is included. Set DEMO_MODE and API_BASE_URL to integrate the expected REST API. The adapter in dist/api.js uses /api/v1 routes. Never commit credentials; session tokens are held in memory. Real backend integration remains unverified.

## Project layout

- dist/app.js — dashboard and review behavior
- dist/signal.css — active storm-instruments theme and interaction styling
- dist/styles.css, world.css, vivid.css — preceding style layers currently retained by the page
- src/Atmosphere.jsx — optimized canvas particle field
- src/motion.jsx — React islands and GSAP scroll choreography
- src/reactbits/ — vendored React Bits components and license
- build.mjs — esbuild motion bundle
- skills/designmaxx/ — customized design skill with Joshua’s preference profile
- DESIGN.md, PRODUCT.md — design and product context

Hosting-specific Sites identity and temporary build archives are deliberately excluded. This is a standalone frontend branch and contains no backend changes.
