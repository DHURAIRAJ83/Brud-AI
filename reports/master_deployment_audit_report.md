# Master Deployment Audit Report — Rudran Tamil AI

**Date:** 2026-06-14  
**Project:** Rudran Tamil AI  
**Auditor:** Senior DevOps Engineer, Docker Architect, & Cyber Security Auditor  
**Verdict:** **NOT READY** (Do NOT deploy to production or push to GitHub in current state)  

---

## 1. Executive Summary

This master audit evaluates the readiness of the **Rudran Tamil AI** project for deployment onto a **Hostinger VPS** (Ubuntu 24.04, 2 vCPUs, 8 GB RAM, existing Ollama & Docker installations) and version control pushing to **GitHub**.

A complete audit of the codebase, container setups, Git configuration, and networking topology was performed. The overall rating is **NOT READY** due to critical security exposures, hardcoded connection strings, and database leakage risks.

### Final Scores
- **Production Readiness Score:** 75 / 100
- **Security Score:** 40 / 100
- **Docker Readiness Score:** 70 / 100
- **Network Security Score:** 50 / 100
- **GitHub Deployment Score:** 60 / 100
- **Combined Audit Score:** **59 / 100** (Fail)

---

## 2. All Discovered Issues & Risk Assessment

### A. Security Vulnerabilities
- **[CRITICAL] Unauthenticated WebSocket Chat:** 
  The chat endpoint `/ws/chat` accepts connections without validating credentials or tokens, allowing unauthorized queries and tool execution in the backend process.
- **[CRITICAL] Unauthenticated System Events Broadcaster:** 
  `/ws/system-events` broadcasts user changes and biometrics template update details publicly, leaking system activity logs to anyone subscribing.
- **[HIGH] Missing REST Auth on Voice Audit Records:** 
  Endpoints for logging voice sessions (`POST /session`), viewing logs (`GET /sessions`), downloading recordings (`GET /audio/{session_id}`), and statistics (`GET /metrics`) lack authentication dependencies.
- **[HIGH] Hardcoded Secret Key Fallbacks:** 
  If `SECRET_KEY` is not set in `.env`, the JWT module falls back to a hardcoded string, which is committed in the Git history. Similarly, the voice biometric HMAC utilizes a fallback key.
- **[HIGH] Admin Backdoor via Configuration Bypass:** 
  If `SECURITY_ENABLED` is turned off, the authentication dependency automatically authenticates all incoming connections as a mock Admin profile, creating an escalation risk in development or debug configurations.
- **[HIGH] Missing default password for seeded admin:** 
  The seeded admin user is created with a blank password hash, locking them out of password authentication but leaving a blank column.
- **[MEDIUM] Trivial Sandbox Bypass in Plugin Uploader:** 
  The AST analyzer in `plugins.py` only blocks standard imports of `os`, `subprocess`, etc., but can be bypassed using `__import__` or `eval()`.
- **[MEDIUM] Rate Limiter Lacks IP Fallback:** 
  Rate limiting only tracks verified API keys; unauthenticated paths are vulnerable to Denial of Service (DoS) attacks.

### B. Network & Infrastructure Configuration
- **[HIGH] Public Port Exposure (Docker Bypass):** 
  Ports 8000 (FastAPI), 3000 (React Frontend), and 3001 (Vite Dashboard) are mapped to `0.0.0.0` in `docker-compose.yml`, exposing them publicly on the VPS IP, bypassing secure Nginx reverse proxy configurations.
- **[HIGH] Container-to-Host Ollama Connection Failure:** 
  The backend's default `.env` references `localhost:11434` for Ollama. Inside the container, this resolves internally, causing connection errors when attempting to query Ollama on the host.
- **[MEDIUM] Hardcoded API Key Mismatch:** 
  The Vite dashboard uses `rudran_86e41d65f9c64383ba471056` as the VITE_API_KEY. This key does not exist in the database and is not configured in `API_KEYS`, locking the dashboard out of the backend.

### C. Git Configuration
- **[HIGH] SQLite Database Exposure:** 
  The root `.gitignore` ignores `memory.db` but does not ignore `agent.db` or `test_agent.db`. These are listed as untracked files and could be committed to GitHub.

---

## 3. Deployment & Security Blockers

### Hostinger VPS Blockers
1. **Ollama URL Resolution:** `http://localhost:11434` will fail from the backend container; it must target the docker bridge gateway IP (`172.17.0.1` or `host.docker.internal`).
2. **2 vCPUs Resource Exhaustion:** Running an 8B LLM on 2 vCPUs will cause high CPU utilization, stalling other API requests. A swap file (at least 4GB) is required.

### Security Blockers
1. **WebSocket Authentication:** `/ws/chat` and `/ws/system-events` must be protected using token validation before accepting connection requests.
2. **REST Route Protection:** `/api/sessions`, `/api/audio/*`, and `/api/metrics` must use `Depends(require_user)` and `Depends(require_admin)`.
3. **Hardcoded Fallbacks:** Hardcoded secrets in `auth_service.py` and `voice_security.py` must be replaced with strict startup validation that raises errors if environment variables are missing.

### Docker Blockers
1. **Exposed Port Bindings:** Port mappings in `docker-compose.yml` must bind to `127.0.0.1` to prevent exposing service ports publicly.
2. **Model Cache Volumes:** Hugging Face and Whisper cache directories must be mounted as host volumes to prevent model files from being downloaded on every container restart.

### GitHub Blockers
1. **Git Database Exposure:** `agent.db` and `test_agent.db` must be added to `.gitignore`.
2. **Codebase Secrets:** Fallback secrets must be removed.

---

## 4. Required & Recommended Fixes

### Required Fixes (Immediate)
1. **Enforce WebSocket Auth:**
   In [stream.py](file:///H:/AI_LLM/Tamil_AI/backend/routes/stream.py#L193):
   Extract and validate the `token` query parameter using `jose.jwt` before accepting the connection.
2. **Enforce Auth on Voice Endpoints:**
   In [voice_sessions.py](file:///H:/AI_LLM/Tamil_AI/backend/routes/voice_sessions.py#L39):
   Add `Depends(require_user)` to `@router.get("/sessions")`, `@router.get("/audio/{session_id}")`, and `@router.get("/metrics")`. Add `Depends(require_admin)` to `/admin/cleanup`.
3. **Resolve Frontend BASE URL:**
   In [api.js](file:///H:/AI_LLM/Tamil_AI/frontend/src/services/api.js#L5):
   Remove the hardcoded `http://localhost:8000/api` base URL and use a relative path `/api` or read from environment variables.
4. **Fix Port Mapping in Compose:**
   In [docker-compose.yml](file:///H:/AI_LLM/Tamil_AI/docker-compose.yml):
   Change host port mappings to `127.0.0.1:3000:3000`, `127.0.0.1:3001:3001`, and `127.0.0.1:8000:8000`.
5. **Ignore databases:**
   In [.gitignore](file:///H:/AI_LLM/Tamil_AI/.gitignore):
   Add `backend/*.db` to prevent database exposures.

### Recommended Fixes (Optimization)
1. **Host Swap File:** Set up a 4GB swap space on the Hostinger Ubuntu VPS to absorb memory spikes during parallel inference.
2. **Centralized Nginx in Docker Compose:** Add an Nginx service in `docker-compose.yml` to handle reverse proxy and SSL configuration, avoiding manual setup on the VPS host.
3. **Container Healthchecks:** Add healthcheck definitions to Compose services to ensure containers are restarted if they become unhealthy.
4. **Ollama API Isolation:** Bind Ollama to `127.0.0.1` on the VPS host, and use the Docker bridge IP for container access.

---

## 5. Final Recommendation

**DO NOT DEPLOY IN CURRENT STATE.**

To proceed safely:
1. Address the required fixes listed in Section 4.
2. Verify that `agent.db` and test databases are added to `.gitignore`.
3. Set up Nginx on the host VPS using the configuration template provided in the Compatibility Report.
4. Set up Let's Encrypt SSL certificates.
5. Create a swap file on the Ubuntu host.
6. Seed a secure admin API key and verify that it matches the key configured in the dashboard.
