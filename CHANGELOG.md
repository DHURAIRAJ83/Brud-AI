# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- **Docker & Port Configuration**: Added dynamic port binding to backend Dockerfile. Added log rotation (`max-size: 10m`, `max-file: 5`) to all Docker Compose services to prevent log bloat.
- **Nginx Dynamic Routing**: Implemented `default.conf.template` to route traffic dynamically using environment variables (`BACKEND_INTERNAL_PORT`, `FRONTEND_INTERNAL_PORT`, `DASHBOARD_INTERNAL_PORT`).
- **Rate Limiting**: Added `rate_limits` table to SQLite database schema in `models/base.py` for persistent, restart-proof rate limiting.
- **Environment Management**: Added comprehensive `.env.local` and `.env.production` templates, and updated `backend/.env.example`.
- **Advanced Health Checks**: Overhauled `/health` endpoint with a strict 2-second timeout to concurrently check the database, FAISS index, and Ollama connection status to prevent deployment hangs.
- **Automated Rollback**: Configured GitHub Actions (`deploy.yml`) to automatically perform health checks and roll back to the previous Git commit and container version if a deployment fails.
- **Backup & Retention**: Enhanced `backup.sh` to support native `sqlite3` backups, container-aware paths, and 7-day retention pruning.
- **Documentation**: Documented future PostgreSQL migration path in `docs/DEPLOYMENT.md`.

### Changed
- Refactored `SecurityMiddleware` and `RateLimiter` in `backend/services/security.py` to be fully asynchronous and backed by SQLite.
- Applied IP-based rate limiting on all public endpoints.
- Updated Docker Compose to mount persistent cache volumes (`hf_cache` and `whisper_cache`) for HuggingFace and Whisper to prevent redownloads on restart.

### Security
- Replaced hardcoded default ports with environment variables.
- Added explicit security logging (`logger.warning`) for failed API keys, JWT failures, and rate limit violations.
