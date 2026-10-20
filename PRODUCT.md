# Monsoon

## Platform
Web. Responsive frontend with a privately hosted Sites deployment.

## Purpose and users
Weather analytics and citizen-report review for analysts, reviewers, and administrators. Public preview shows verified reports. Core tasks: filter reports by date period, location, event type, and verification status; inspect geographic activity and event counts; inspect evidence metadata; verify, reject, retract, or reopen reports according to role; export filtered reports.

## Product truth
The current release is an interactive frontend demonstration. Reports and source health are labeled sample data. Demo moderation changes persist in the browser. No actual AI classifier, duplicate-detection model, or ingestion worker runs in this frontend.

The reference is the Weather Analytics Frontend Handover and API Contract supplied by the user. REST access uses a configurable backend origin plus /api/v1. Weather providers are not queried directly. Bearer tokens remain in memory. Human reviewer verification is separate from model suggestions and provider trust. Public reports omit private contact data and evidence links.

## Stack
Static HTML/CSS/JS dashboard with React animation islands, GSAP ScrollTrigger, and vendored React Bits components. esbuild creates dist/motion.js. npm run build builds; npm run check checks syntax; npm run dev serves the dist directory on port 5173. Backend integration is configurable in dist/config.js and has not been verified against a running API.

## Current design request

The user approved the storm-instruments edition: dark charcoal, strong signal orange and amber, Barlow Condensed headings, Hanken Grotesk controls, smooth particle storytelling and meaningful interactions throughout the dashboard. The optional stone light theme persists through a toolbar toggle. The designmaxx skill records the user’s preferences.
