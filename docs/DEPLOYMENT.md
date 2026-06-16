# Rudran AI - Deployment Guide

This guide covers the automated deployment of Rudran AI using Docker Compose.

## 1. Prerequisites
- Docker Engine & Docker Compose installed.
- (Optional) NVIDIA Docker toolkit if running local LLMs on GPU.

## 2. Environment Configuration
Create a `.env` file in the root directory:
```env
# Backend
SECURITY_ENABLED=True
OLLAMA_BASE_URL=http://host.docker.internal:11434
UPLOAD_DIR=/app/uploads

# Dashboard
VITE_API_KEY=rudran_your_admin_api_key
```

## 3. Starting the Services

Run the included `docker-compose.yml` to spin up all 3 services (Backend, Frontend, Dashboard) in detached mode:

```bash
docker-compose up -d --build
```

### Accessing the System
- **Backend API:** `http://localhost:8000`
- **React Chat UI:** `http://localhost:3000`
- **Ops Dashboard:** `http://localhost:3001`

## 4. Backups and Rollbacks

Two shell scripts are provided in the `scripts/` directory:
- `./scripts/backup.sh`: Creates a compressed tarball of the SQLite databases (`memory.db`, `agent.db`) and user uploads.
- `./scripts/rollback.sh <backup_file>`: Stops the Docker containers, restores the databases from the backup archive, and restarts the services.

We recommend configuring a daily cron job to run `backup.sh`.

## 5. Future PostgreSQL Migration Path

Currently, Rudran AI uses SQLite (`agent.db` and `memory.db`) for zero-configuration deployments. For high-availability, multi-node deployments, migrating to PostgreSQL is supported.

### Migration Steps:
1. Spin up a PostgreSQL container or managed service.
2. Update `.env.production`:
   ```env
   # Replace sqlite connection with postgres
   # DATABASE_URL=sqlite:////app/data/agent.db
   DATABASE_URL=postgresql+asyncpg://user:password@host:5432/rudran
   ```
3. Update `backend/requirements.txt` to include `asyncpg` and `psycopg2-binary`.
4. Update `models/base.py` to initialize an async SQLAlchemy engine instead of `aiosqlite`.
5. Run a one-time data migration script to copy rows from SQLite `agent.db` to PostgreSQL.
6. Remove `AGENT_DB_PATH` and `MEMORY_DB_PATH` from environment configurations.
