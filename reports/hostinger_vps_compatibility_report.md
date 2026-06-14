# Hostinger VPS Compatibility Report — Rudran Tamil AI

**Target Host Configuration:**
- **Hosting Provider:** Hostinger VPS
- **OS:** Ubuntu 24.04 LTS (Noble Numbat)
- **Compute:** 2 vCPUs
- **Memory:** 8 GB RAM
- **AI Runtime:** Existing Ollama installation on host
- **Containerization:** Existing Docker installation on host

---

## 1. Resource Consumption Estimation

### A. CPU Requirements
- **Ollama LLM Inference (Mistral-7B / Qwen-8B):**
  - **Status:** **CRITICAL CONSTRAINT**
  - **Detail:** Running an 8B parameterized LLM on 2 vCPUs without GPU acceleration is extremely compute-heavy. During active text generation, CPU utilization will spike to 100% on both cores. Expected generation speed is slow (estimated at **1–3 tokens per second**).
  - **Impact:** Parallel user requests will queue up and experience major latency spikes. FastAPI worker threads and static file hosting servers will face starvation, causing delayed response cycles.
- **Biometrics (MFCC/CMVN) & Embeddings (`all-MiniLM-L6-v2`):**
  - **Status:** **COMPATIBLE**
  - **Detail:** The embedding model is small (22M parameters) and takes less than 50ms of CPU time per RAG chunk search. The MFCC speaker verification calibration is also extremely fast.
- **Voice STT (Whisper Base INT8):**
  - **Status:** **MODERATE CONSTRAINT**
  - **Detail:** Whisper's transcription runs on CPU with `int8` quantization. A 10-second WAV file will take roughly 2 seconds to transcribe. Parallel transcription requests will cause bottlenecking.

### B. RAM Usage Estimation
To run all system processes concurrently, the memory layout is estimated as follows:

| Component | RAM Estimate (MB) | Details / Quantization |
| :--- | :--- | :--- |
| **Ubuntu 24.04 OS & Docker Daemon** | 1,200 MB | Base system overhead |
| **Ollama Service (Mistral-7B / Qwen-8B)** | 4,800 MB | Q4_K_M (4-bit quantized) memory footprint |
| **Sentence-Transformers (Embeddings)** | 300 MB | CPU load memory footprint |
| **Faster-Whisper (STT Base Model)** | 150 MB | CTranslate2 INT8 model cache |
| **FastAPI Backend (rudran_backend)** | 180 MB | Single worker + SQLite memory mapping |
| **Frontend Container (serve)** | 50 MB | Static assets serve |
| **Dashboard Container (serve)** | 50 MB | Static assets serve |
| **Nginx Web Server & Buffer Caches** | 100 MB | Connection buffers |
| **SQLite WAL Memory Pool** | 120 MB | Temporary memory maps for concurrency |
| **Total Estimated RAM** | **~6.95 GB** | **Safety Margin: ~1.05 GB** |

- **Compatibility Verdict:** **COMPATIBLE BUT VERY TIGHT**
  - Running within 8GB RAM is possible, but leaves little buffer. If Ollama runs unquantized models or if more than 1 model is loaded into memory (e.g. tinyllama + mistral loaded at the same time), the system will exceed 8GB and trigger the Linux Out-Of-Memory (OOM) killer, terminating the Ollama or FastAPI process.
  - **Recommendation:** Enable a **4GB swap file** on the Ubuntu host immediately to absorb memory spikes.

### C. Storage Requirements
- **Operating System + Docker Base Images:** ~3.0 GB
- **Ollama Models (`mistral` + `qwen3` / `llama3`):** ~9.0 GB (4.5 GB each)
- **Sentence-Transformers model (`all-MiniLM-L6-v2`):** ~120 MB
- **Faster-Whisper base model:** ~74 MB
- **WAV Voice Session Audio Cache (Uptrend):** Assuming ~176 KB/sec WAV audio, 10,000 recorded sessions of 5s average duration consumes **~8.8 GB** of storage.
- **SQLite Database files (`agent.db` + `memory.db`):** <500 MB
- **Total Storage Footprint:** **~21 GB**
- **Verdict:** Fully compatible with standard Hostinger VPS SSD quotas (usually 50GB to 100GB).
  - **Recommendation:** Implement a cron cleanup script to purge `backend/uploads/voice_cache/*.wav` older than 7 days to prevent disk exhaustion.

---

## 2. Infrastructure & Routing Compatibility

### A. Ollama Integration (Container-to-Host Communication)
- **Constraint:** Ollama runs directly on the VPS host, while the backend runs inside the `rudran_backend` container.
- **Problem:** Configured `OLLAMA_BASE_URL=http://localhost:11434` inside the container will look for Ollama *within* the container, resulting in a connection failure.
- **Fix:** In Linux, the docker bridge gateway defaults to `172.17.0.1`. The backend should connect to `http://172.17.0.1:11434` or use the Compose `extra_hosts` configuration to resolve `host.docker.internal` to the host's bridge IP.

### B. Nginx Reverse Proxy Compatibility
To host all three services under ports 80/443, Nginx must be configured on the host to route traffic correctly:

```nginx
# Proposed Nginx Configuration for Hostinger VPS
server {
    listen 80;
    server_name tamilai.example.com; # Replace with target domain / IP
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name tamilai.example.com;

    ssl_certificate /etc/letsencrypt/live/tamilai.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/tamilai.example.com/privkey.pem;

    # 1. Frontend Static Application
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # 2. Vite Dashboard Application
    location /dashboard {
        proxy_pass http://127.0.0.1:3001/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # 3. FastAPI REST Backend API
    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 4. WebSocket Streaming API (Phase 5 real-time chat)
    location /api/ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### C. SSL Readiness
- Ubuntu 24.04 is fully compatible with Certbot and Let's Encrypt.
- Ports 80 and 443 must be opened on the Hostinger VPS firewall (`ufw allow 80/tcp`, `ufw allow 443/tcp`) to complete the HTTP-01 challenge for SSL certificate generation.
