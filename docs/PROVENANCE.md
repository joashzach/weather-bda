# Source provenance

This repository assembles the existing Monsoon frontend and the locally integrated Weather BDA backend as of 21 October 2026.

The backend started from Weather BDA source commit `9dd77d7b41cd95e864a03000e7a6f0d8600dc588`, downloaded separately as an archive. This import includes the subsequent local changes: public source attribution fields, server pagination for analysis/admin/history collections, and corrected rate-limit retry timing. Those changes are already applied in `backend/`; no additional patch application is necessary.

The frontend is imported from the working application, including the API-connected P0–P3 functionality. The source layout preserves editable `dist/` modules and the React animation build. Third-party React Bits notices are retained.

Machine-specific runtime launchers, installed dependencies, credentials, PostgreSQL binaries and data, QA account tokens, logs, and private test results are intentionally excluded. The acceptance report describes the earlier local environment and references some artifacts that remain outside this repository.
