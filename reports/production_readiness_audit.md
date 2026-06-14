# Production Readiness Audit — Rudran Tamil AI

**Date of Audit:** 2026-06-14  
**Auditor:** Senior DevOps & Security Engineer  
**Project:** Rudran Tamil AI  

This document evaluates the system components, build states, testing frameworks, and overall deployment readiness of the Rudran Tamil AI project.

---

## 1. Backend Startup Status

- **Startup Execution Flow:** 
  The FastAPI application entry point in [main.py](file:///H:/AI_LLM/Tamil_AI/backend/main.py) uses an `asynccontextmanager` lifecycle hook. On startup, the backend automatically triggers:
    1. Critical environment variables check (`validate_environment()`).
    2. Lazy initialization of global caching service (`cache_service.init()`).
    3. Initialization of async SQLite persistent memory tables (`sqlite_memory.init()`).
    4. Setup of typed persistent memory store (`memory_store.init()`).
    5. Discovery of local and cloud Ollama instances (`runtime_manager.startup()`).
    6. Main agent SQLite connection pool setup (`db_manager.init()`).
    7. Database write access validation (`validate_db_writable()`).
    8. Pre-seeding of default admin user (`UserModel.ensure_default_user()`).
    9. Spawning of background tasks for device heartbeat cleanup and voice session purges.
- **Startup Integrity:** **PASSED WITH CONCERNS**
  - **Uvicorn Server Binds:** Default launcher in `main.py` binds to `0.0.0.0:8000`, which opens the port publicly.
  - **Dependency Verification:** Core libraries (`langdetect`, `sentence-transformers`, `faiss`, `aiosqlite`, `faster-whisper`, `python-jose`, `passlib`) are present in [requirements.txt](file:///H:/AI_LLM/Tamil_AI/backend/requirements.txt) and load correctly during startup checks.
  - **Ollama Probe Latency:** If local Ollama is offline (as tested during our active probe), the `runtime_manager.startup()` probe block introduces a 4.0-second delay per host check, resulting in a delayed startup sequence.

---

## 2. Frontend Build Status

- **Framework:** React 18 (`react-scripts` v5)
- **Compilation Check:** **PENDING / ACTIVE**
- **Critical Findings:**
  - **Hardcoded Endpoint URL:** The API connector in [api.js](file:///H:/AI_LLM/Tamil_AI/frontend/src/services/api.js#L5) hardcodes the backend URL:
    ```javascript
    const BASE = 'http://localhost:8000/api';
    ```
    This completely blocks remote deployments. When deployed on the Hostinger VPS, any client web browser loading the page will try to query `localhost:8000` (i.e. the client's own machine) instead of the VPS public IP.
  - **CORS Config Block:** The backend's [main.py](file:///H:/AI_LLM/Tamil_AI/backend/main.py#L174-L188) CORS configuration allows specific origins (including `http://72.61.238.200` and `http://localhost:3000`), but does not cover dynamic hostname bindings, which could cause CORS 400 Bad Request errors on deployment (similar to those recorded in `cors_debug.log`).

---

## 3. Dashboard Build Status

- **Framework:** React 19 + Vite v8 + Tailwind CSS v4
- **Compilation Check:** **PASSED**
  - Successfully built using `npm run build` in 9.78 seconds.
  - Assets generated:
    - `dist/index.html` (0.45 kB)
    - `dist/assets/index-SW5e3316.css` (38.85 kB)
    - `dist/assets/index-CNoGj_8k.js` (316.38 kB)
- **Critical Findings:**
  - **Proxy Configuration Discrepancy:** The [vite.config.ts](file:///H:/AI_LLM/Tamil_AI/dashboard/vite.config.ts#L19-L24) routes `/api` to `http://localhost:8000` during local development. However, the production build runs `serve -s dist -p 3001` (configured in [Dockerfile](file:///H:/AI_LLM/Tamil_AI/dashboard/Dockerfile#L15)), which has no built-in proxy mechanism. Therefore, the dashboard will fail to reach the API in production unless Nginx handles proxying at the network level.
  - **API Key Hardcoding:** The dashboard's API connection in [api.ts](file:///H:/AI_LLM/Tamil_AI/dashboard/src/services/api.ts#L18) pulls the key from `import.meta.env.VITE_API_KEY`. If not configured, it fails. The default `.env.local` contains `VITE_API_KEY=rudran_86e41d65f9c64383ba471056`.

---

## 4. Test Suite Integrity

- **Framework:** Pytest + Pytest-Asyncio (configured via [pytest.ini](file:///H:/AI_LLM/Tamil_AI/backend/pytest.ini))
- **Test Coverage:** Extensive coverage over action planning, coding agents, error translations, RAG retrieval, runtime modes, voice STT, biometrics, and VS Code extension integration.
- **Verification Results:** **FAILED (HUNG)**
  - **Success Cases:** Individual lightweight tests like `test_error_translator.py` and `test_voice_biometrics_infra.py` passed successfully (biometrics test suite completed all 4 cases in 25.70 seconds).
  - **Hang Cause:** Running the full test suite (`python -m pytest`) hangs. This occurs because:
    1. Tests like `test_system.py` and `test_hybrid_rag_and_planner.py` load the `RAGEngine`, which triggers downloading the `all-MiniLM-L6-v2` embedding model (~120MB) from Hugging Face if not cached.
    2. Certain test cases do not mock Ollama calls, attempting connections to `localhost:11434`. Since Ollama is offline, the tests block on multiple HTTP connection timeouts.
    3. Lifespan background tasks (`device_cleanup_loop`, `voice_cleanup_loop`) are not terminated by test fixtures, leaking async tasks and preventing the test suite process from clean termination.

---

## 5. Environment Configuration

- **Backend Configuration:** Managed by Pydantic Settings in [config.py](file:///H:/AI_LLM/Tamil_AI/backend/config.py) and loaded from `backend/.env`.
- **Issues:**
  - `SECRET_KEY` is not enforced during development (falls back to a hardcoded testing key).
  - No `API_KEYS` are defined in the default `backend/.env` file.
  - Development configuration maps to `APP_ENV=development`, but lacks separate production environments config mappings.

---

## 6. Production Deployment Readiness

- **Verdict:** **NOT READY**
  - **Blocker 1 (Frontend):** Hardcoded `http://localhost:8000` base URL prevents client-to-server connectivity.
  - **Blocker 2 (Dashboard):** Vite proxy configurations are local-only; static file serve lacks routing mechanisms for the `/api` target.
  - **Blocker 3 (Security):** Key security endpoints (WebSocket, voice files) are completely unprotected.
  - **Blocker 4 (Git):** SQLite database files `agent.db` are untracked and exposed to commits.
