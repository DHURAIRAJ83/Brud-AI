# Security Audit Report — Rudran Tamil AI

**Date of Audit:** 2026-06-14  
**Audit Standard:** OWASP Top 10 / Production Security Benchmarks  
**Status:** **FAIL (Multiple Critical Vulnerabilities)**  

---

## Vulnerability Summary Table

| ID | Component | Description | Severity | File Reference |
| :--- | :--- | :--- | :--- | :--- |
| **SEC-01** | WebSocket | Unauthenticated Chat WebSocket Endpoint | **CRITICAL** | [stream.py:L193-239](file:///H:/AI_LLM/Tamil_AI/backend/routes/stream.py#L193-L239) |
| **SEC-02** | WebSocket | Unauthenticated System Events Broadcaster | **CRITICAL** | [stream.py:L269-281](file:///H:/AI_LLM/Tamil_AI/backend/routes/stream.py#L269-L281) |
| **SEC-03** | REST API | Missing Authentication on Voice Audit & Audio Logs | **HIGH** | [voice_sessions.py:L39-180](file:///H:/AI_LLM/Tamil_AI/backend/routes/voice_sessions.py#L39-L180) |
| **SEC-04** | Auth | Hardcoded Default Security Fallback Keys | **HIGH** | [auth_service.py:L26](file:///H:/AI_LLM/Tamil_AI/backend/services/auth_service.py#L26) / [voice_security.py:L20](file:///H:/AI_LLM/Tamil_AI/backend/security/voice_security.py#L20) |
| **SEC-05** | Auth | Security Bypass Admin Backdoor | **HIGH** | [auth_service.py:L147-157](file:///H:/AI_LLM/Tamil_AI/backend/services/auth_service.py#L147-L157) |
| **SEC-06** | Database | SQLite Admin Credentials Database Untracked in Git | **HIGH** | [.gitignore](file:///H:/AI_LLM/Tamil_AI/.gitignore) |
| **SEC-07** | Admin | Blank Password for Default Seed Admin User | **HIGH** | [user.py:L135-147](file:///H:/AI_LLM/Tamil_AI/backend/models/user.py#L135-L147) |
| **SEC-08** | Sandbox | Trivial Sandbox Bypass in Custom Plugin Uploader | **MEDIUM** | [plugins.py:L56-74](file:///H:/AI_LLM/Tamil_AI/backend/routes/plugins.py#L56-L74) |
| **SEC-09** | Rate Limit | Rate Limiter Lacks IP Fallback / Disabled entirely by Config | **MEDIUM** | [security.py:L144-216](file:///H:/AI_LLM/Tamil_AI/backend/services/security.py#L144-L216) |

---

## Detailed Findings

### SEC-01: Unauthenticated Chat WebSocket Endpoint
- **Severity:** **CRITICAL**
- **File Reference:** [backend/routes/stream.py:L193-239](file:///H:/AI_LLM/Tamil_AI/backend/routes/stream.py#L193-L239)
- **Description:** 
  The WebSocket router `@router.websocket("/ws/chat")` immediately executes `await websocket.accept()` without inspecting any authentication headers, query parameters, or JWT tokens. 
  Although the frontend [api.js](file:///H:/AI_LLM/Tamil_AI/frontend/src/services/api.js#L200-L202) attempts to send a `?token=` parameter, the backend socket loop completely ignores it.
- **Risk:** 
  Any malicious actor can establish a socket connection, send messages, interact with RAG/Memory, and trigger tool/plugin executions in the server process without credentials.

---

### SEC-02: Unauthenticated System Events Broadcaster
- **Severity:** **CRITICAL**
- **File Reference:** [backend/routes/stream.py:L269-281](file:///H:/AI_LLM/Tamil_AI/backend/routes/stream.py#L269-L281)
- **Description:** 
  The WebSocket endpoint `/ws/system-events` accepts connections globally and registers clients into `system_events_manager`.
- **Risk:** 
  An unauthenticated attacker can listen to live system notifications containing sensitive user information (e.g., username, user ID) broadcasted during logins or biometrics updates.

---

### SEC-03: Missing Authentication on Voice Audit & Audio Logs
- **Severity:** **HIGH**
- **File Reference:** [backend/routes/voice_sessions.py:L39-180](file:///H:/AI_LLM/Tamil_AI/backend/routes/voice_sessions.py#L39-L180)
- **Description:** 
  The REST endpoints for logging sessions (`POST /session`), listing audit logs (`GET /sessions`), downloading raw voice files (`GET /audio/{session_id}`), and viewing statistics (`GET /metrics`) contain no dependency injection locks (`Depends(require_user)`).
- **Risk:** 
  Allows any unauthenticated network client to browse the voice logs history and download raw speaker WAV recording files.

---

### SEC-04: Hardcoded Default Security Fallback Keys
- **Severity:** **HIGH**
- **File Reference:** [backend/services/auth_service.py:L26](file:///H:/AI_LLM/Tamil_AI/backend/services/auth_service.py#L26) & [backend/security/voice_security.py:L20](file:///H:/AI_LLM/Tamil_AI/backend/security/voice_security.py#L20)
- **Description:** 
  If `SECRET_KEY` is not defined in `.env`, the JWT authentication falls back to `"dev-local-secret-fallback-key-for-testing-only"`. Similarly, the voice biometric signer falls back to `"rudran_voice_secret_fallback_key_2026"`.
- **Risk:** 
  If the application is deployed with misconfigured host environments, default keys will be active. Attackers can forge valid JWTs or sign malicious speaker embeddings.

---

### SEC-05: Security Bypass Admin Backdoor
- **Severity:** **HIGH**
- **File Reference:** [backend/services/auth_service.py:L147-157](file:///H:/AI_LLM/Tamil_AI/backend/services/auth_service.py#L147-L157)
- **Description:** 
  If `security_enabled` is set to `False` in the settings, the authentication dependency `get_current_user` completely bypasses verification and returns a hardcoded administrator mock profile:
  ```python
  if not _settings.security_enabled:
      return {
          "id": "admin-user-123",
          "username": "admin",
          "role": "admin",
          "display_name": "Admin",
          "email": "admin@example.com"
      }
  ```
- **Risk:** 
  If an administrator turns off `SECURITY_ENABLED` during testing on the production server, the system automatically treats *every* request as an administrative command execution.

---

### SEC-06: SQLite Admin Credentials Database Untracked in Git
- **Severity:** **HIGH**
- **File Reference:** [.gitignore](file:///H:/AI_LLM/Tamil_AI/.gitignore)
- **Description:** 
  The main SQLite database [agent.db](file:///H:/AI_LLM/Tamil_AI/backend/agent.db) contains users, passwords, sessions, devices, and dynamic voice profiles. The root `.gitignore` file ignores `memory.db` but completely omits `agent.db` and `test_agent.db`.
- **Risk:** 
  `agent.db` is currently listed as an untracked file. A broad commit (`git add .`) will upload the SQLite file to GitHub, leaking registered user profiles and security logs.

---

### SEC-07: Blank Password for Default Seed Admin User
- **Severity:** **HIGH**
- **File Reference:** [backend/models/user.py:L135-L147](file:///H:/AI_LLM/Tamil_AI/backend/models/user.py#L135-L147)
- **Description:** 
  The startup hook `ensure_default_user()` seeds the initial administrative user using `UserModel.create(UserCreate(username="admin", role=UserRole.ADMIN))`. However, `UserModel.create` does not support or set a password field.
- **Risk:** 
  The database creates the `admin` user with an empty password hash (`hashed_password` = `""`). The user cannot log in via password, but this leaves a blank field in the DB.

---

### SEC-08: Trivial Sandbox Bypass in Custom Plugin Uploader
- **Severity:** **MEDIUM**
- **File Reference:** [backend/routes/plugins.py:L56-74](file:///H:/AI_LLM/Tamil_AI/backend/routes/plugins.py#L56-L74)
- **Description:** 
  The AST parser inspects uploaded Python plugins for imports of `os`, `subprocess`, `pty`, and `shlex` and checks for calls to `.system()`, `.popen()`, and `.spawn()`.
  However, standard Python features like:
  ```python
  os = __import__('o' + 's')
  os.system('id')
  ```
  or using builtins like `eval()` and `exec()` completely bypass the AST attribute and import node checks.
- **Risk:** 
  A compromised admin account can upload a malicious Python plugin, bypass the AST check, and execute arbitrary commands directly on the host VPS.

---

### SEC-09: Rate Limiter Lacks IP Fallback
- **Severity:** **MEDIUM**
- **File Reference:** [backend/services/security.py:L144-216](file:///H:/AI_LLM/Tamil_AI/backend/services/security.py#L144-L216)
- **Description:** 
  `SecurityMiddleware` applies sliding-window rate limiting using the validated API key. If the API key is missing or security is disabled, no rate limiting is enforced on IP addresses.
- **Risk:** 
  Unauthenticated endpoints (like health/docs) are vulnerable to Denial of Service (DoS) attacks.
