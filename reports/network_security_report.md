# IPv4 & Network Security Report — Rudran Tamil AI

**Date of Audit:** 2026-06-14  
**Target Host Configuration:** Hostinger VPS (Ubuntu 24.04)  
**Status:** **FAIL (Network Leaks Detected)**  

---

## 1. Port Exposure Mapping

The system requires that only public ports **22** (SSH), **80** (HTTP), and **443** (HTTPS) be exposed to the internet. Ports used by applications and backend components must remain private.

Below is the verified port mapping based on the active codebase configuration:

| Component | Target Port | Status in Code | Public Exposure Risk | Action Required |
| :--- | :--- | :--- | :--- | :--- |
| **SSH** | 22 | Host Config | Restricted to Admin IPs | Restrict in UFW |
| **HTTP (Nginx)** | 80 | Host Config | **OPEN** (For Let's Encrypt / Redirect) | Allow in UFW |
| **HTTPS (Nginx)** | 443 | Host Config | **OPEN** (Production Entry Point) | Allow in UFW |
| **FastAPI Backend** | 8000 | `0.0.0.0:8000:8000` | **EXPOSED** (Accessible on public IP) | Bind port to `127.0.0.1` |
| **Ollama Service** | 11434 | Host Config | **EXPOSED** (If bound to `0.0.0.0`) | Bind Ollama to `127.0.0.1` |
| **React Frontend** | 3000 | `3000:3000` | **EXPOSED** (Accessible on public IP) | Bind port to `127.0.0.1` |
| **Vite Dashboard** | 3001 | `3001:3001` | **EXPOSED** (Accessible on public IP) | Bind port to `127.0.0.1` |
| **SQLite Databases**| N/A | File-based | **NO EXPOSURE** (Direct file access) | Exclude from Git tracking |

---

## 2. Detailed Port Exposure & Binding Checks

### A. FastAPI Port 8000 Binding
- **Finding:** 
  The [docker-compose.yml](file:///H:/AI_LLM/Tamil_AI/docker-compose.yml#L9-L10) file defines backend ports as:
  ```yaml
  ports:
    - "8000:8000"
  ```
  And [main.py](file:///H:/AI_LLM/Tamil_AI/backend/main.py#L306) starts Uvicorn with:
  ```python
  uvicorn.run("main:app", host="0.0.0.0", port=8000)
  ```
- **Vulnerability:** 
  By exposing `"8000:8000"` on all host interfaces (`0.0.0.0`), Docker bypasses host UFW firewalls on Linux. Anyone can access `http://<vps-ip>:8000/docs` directly, bypassing Nginx completely.
- **Fix:** 
  Modify `docker-compose.yml` to bind the port locally to the loopback interface:
  ```yaml
  ports:
    - "127.0.0.1:8000:8000"
  ```
  Or remove the `ports` block completely and rely on Docker network aliases if Nginx is containerized on the same bridge network.

### B. Ollama Service Port 11434 Binding
- **Finding:** 
  Ollama is installed directly on the Hostinger VPS host.
- **Vulnerability:** 
  If Ollama's host environment configuration is set to `OLLAMA_HOST=0.0.0.0` to allow the docker container to connect, port 11434 will be exposed publicly. Anyone can send prompt requests to the VPS Ollama service.
- **Fix:** 
  1. Keep Ollama bound to the host local interface `OLLAMA_HOST=127.0.0.1:11434`.
  2. Configure the container backend to use the Docker bridge interface IP (`172.17.0.1` or dynamically resolved `host.docker.internal`) to query the host's Ollama instance.

### C. Docker Network Isolation Policy
- **Finding:** 
  Services are connected via `rudran_network` bridge driver.
- **Vulnerability:** 
  Although the bridge network allows private name resolution (e.g. backend container can be resolved as `backend`), the `ports` section publishes frontend (`3000`) and dashboard (`3001`) publicly.
- **Fix:** 
  Restrict all published ports in `docker-compose.yml` to `127.0.0.1` (e.g. `"127.0.0.1:3000:3000"`, `"127.0.0.1:3001:3001"`).

### D. Nginx Reverse Proxy Routing Requirements
- **Nginx Setup:** 
  Nginx on the Hostinger host must intercept all external requests on port 80/443. It should proxy traffic locally to the Docker container endpoints:
  - `/` -> `127.0.0.1:3000` (Frontend)
  - `/dashboard` -> `127.0.0.1:3001` (Dashboard)
  - `/api` -> `127.0.0.1:8000` (FastAPI backend)
  - `/api/ws` -> `127.0.0.1:8000` (FastAPI WebSocket upgrade)
- **Header Forwarding:** 
  Nginx must inject the original client IP headers:
  ```nginx
  proxy_set_header X-Real-IP $remote_addr;
  proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  ```
  If headers are not passed, the backend rate limiter and audit logs will only record the loopback IP `127.0.0.1` for all user commands.
