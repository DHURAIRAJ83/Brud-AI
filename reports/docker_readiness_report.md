# Docker Readiness Report — Rudran Tamil AI

**Date of Audit:** 2026-06-14  
**Docker Readiness Score:** **70/100**  
**Verdict:** **ALPHA READY (Requires Improvements Before Production)**  

---

## 1. Containerization Audit Checklist

| Item | Status | Finding / Detail | Recommendation |
| :--- | :--- | :--- | :--- |
| **Backend Dockerfile** | **GOOD** | Multi-stage image running `python:3.11-slim`, installs `ffmpeg` for Whisper, quantizes dependencies. | None. |
| **Frontend Dockerfile** | **GOOD** | Builds via `node:20-alpine`, runs static server (`serve`) on port 3000. | Use a smaller runtime or multi-stage Nginx build to serve static assets directly. |
| **Dashboard Dockerfile** | **GOOD** | Builds via `node:20-alpine`, runs static server (`serve`) on port 3001. | Same as frontend. |
| **Compose Orchestration** | **GOOD** | Integrates all three services under a single `docker-compose.yml` file. | Expose ports on `127.0.0.1` rather than `0.0.0.0`. |
| **Environment Injection** | **FAIR** | Backend reads `.env` dynamically via `env_file`. Dashboard reads `.env.local` dynamically. | Dashboard build environment needs Vite build-time injections. |
| **Volume Persistence** | **GOOD** | Maps agent/memory SQLite databases and uploads/plugins folders cleanly. | Ensure user permissions match host folders. |
| **Restart Policies** | **GOOD** | Uses `restart: unless-stopped` for all services. | None. |
| **Container Health Checks** | **MISSING** | No health checks defined in docker-compose or Dockerfiles. | Add `healthcheck` block to compost services. |
| **Container Networking** | **FAIR** | Custom bridge network `rudran_network` active. | Avoid public ports exposure. |

---

## 2. Detailed Findings

### A. Missing Container Health Checks
- **Finding:** 
  The current [docker-compose.yml](file:///H:/AI_LLM/Tamil_AI/docker-compose.yml) lacks `healthcheck` declarations. If the backend fails to connect to SQLite or hangs on Ollama requests, the container will remain in `running` status, and Docker will not trigger a restart.
- **Fix:** 
  Add a healthcheck block to the backend service in `docker-compose.yml`:
  ```yaml
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 15s
  ```

### B. Embedding Cache Persistence Issue
- **Finding:** 
  On startup, the RAG engine loads `sentence-transformers/all-MiniLM-L6-v2` and Whisper downloads the `base` language model. These models are fetched from Hugging Face and saved to the container's root directory (`~/.cache/huggingface` and standard directories).
- **Vulnerability:** 
  Since these cache directories are not volume-mounted in the compose file, **restarting or rebuilding the container wipes the model files**. The container must download ~200MB of model files on every deployment/restart, causing high startup latency and network bandwidth waste.
- **Fix:** 
  Map the huggingface and cache directories to host storage in `docker-compose.yml`:
  ```yaml
  volumes:
    - ./backend/models:/app/models
    - hf_cache:/root/.cache/huggingface
  ```

### C. Host Network Port Exposure
- **Finding:** 
  All services bind ports directly to the host's `0.0.0.0` interface.
- **Vulnerability:** 
  Exposes application ports 3000, 3001, and 8000 to the public, bypassing firewall rules.
- **Fix:** 
  Change port bindings to limit accessibility to host loopback interfaces:
  ```yaml
  ports:
    - "127.0.0.1:8000:8000"
  ```
  Or remove ports completely and route traffic through an Nginx container on the same network.
