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
