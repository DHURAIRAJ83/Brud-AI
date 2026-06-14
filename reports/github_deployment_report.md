# GitHub Deployment Report — Rudran Tamil AI

**Date of Audit:** 2026-06-14  
**Audit Scope:** Git Tracking & Sensitive Files Leaks  
**Status:** **FAIL (Active Database Exposure)**  

---

## 1. Git Ignore Rules Audit

An inspection of the root [.gitignore](file:///H:/AI_LLM/Tamil_AI/.gitignore) was conducted to verify that sensitive files are excluded from git tracking.

Below is the verification status for each sensitive file category:

| File / Folder Path | Excluded in `.gitignore`? | Git Status | Risk Verdict |
| :--- | :--- | :--- | :--- |
| **`backend/.env`** | **YES** (via `.env` pattern) | Untracked (Ignored) | **SAFE** |
| **`dashboard/.env.local`** | **YES** (via `.env.local` pattern) | Untracked (Ignored) | **SAFE** |
| **`backend/memory.db`** | **YES** (via `memory.db` pattern) | Untracked (Ignored) | **SAFE** |
| **`backend/agent.db`** | **NO** | **Untracked (NOT IGNORED)** | **CRITICAL LEAK RISK** |
| **`backend/test_agent.db`** | **NO** | **Untracked (NOT IGNORED)** | **CRITICAL LEAK RISK** |
| **`backend/uploads/`** | **YES** (via `uploads/` pattern) | Untracked (Ignored) | **SAFE** |
| **`backend/venv/`** | **YES** (via `venv/` pattern) | Untracked (Ignored) | **SAFE** |
| **`backend/usage_log.jsonl`**| **YES** (via `usage_log.jsonl` pattern)| Untracked (Ignored) | **SAFE** |
| **`backend/*.log`** | **YES** (via `*.log` pattern) | Untracked (Ignored) | **SAFE** |

---

## 2. Critical Leak Analysis

### A. SQLite Database Leak Risk (agent.db)
- **Vulnerability:** 
  The primary SQLite database [agent.db](file:///H:/AI_LLM/Tamil_AI/backend/agent.db) is located in the `backend/` folder. While `memory.db` is explicitly ignored by [.gitignore](file:///H:/AI_LLM/Tamil_AI/.gitignore#L8), `agent.db` is **NOT** ignored.
- **Risk:** 
  If the user runs `git add .` or `git add backend/` during staging, the live `agent.db` file will be checked into the repository and pushed to GitHub. This database contains:
    - Registered user accounts with display names and emails.
    - Active API keys (e.g. `rudran_<hash>`).
    - Device registrations with details.
    - Commands history and audit logs.
  Checking this file into a public repository will expose security credentials.
- **Fix:** 
  Add `agent.db` and `test_agent.db` explicitly to the root `.gitignore`:
  ```gitignore
  # SQLite Databases
  *.db
  ```

### B. Fallback Secrets in Codebase
- **Vulnerability:** 
  The codebase contains fallback secrets that are tracked in Git:
  - In [auth_service.py:L26](file:///H:/AI_LLM/Tamil_AI/backend/services/auth_service.py#L26):
    `SECRET_KEY = _settings.secret_key or "dev-local-secret-fallback-key-for-testing-only"`
  - In [voice_security.py:L20](file:///H:/AI_LLM/Tamil_AI/backend/security/voice_security.py#L20):
    `"rudran_voice_secret_fallback_key_2026"`
- **Risk:** 
  If the host environment fails to load `.env` correctly, these fallback strings will be used as security keys. Since these strings are committed to Git, an attacker who reads the code can decrypt JWT tokens or sign biometric vectors.
- **Fix:** 
  Remove the fallback strings. If the keys are missing from the configuration settings, raise a `RuntimeError` immediately on startup, forcing the application to halt.
