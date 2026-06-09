# 🤖 Tamil AI Assistant

A CPU-friendly, fully offline Tamil + English AI assistant with:
- 💬 Chat interface (Tamil & English)
- 🔍 Intent Detection Engine
- 🛠️ Tool Engine (summarize, calculate, translate, file read)
- 📚 RAG System (PDF/DOCX/TXT knowledge base)
- 🧠 Session Memory
- ⚙️ Admin Panel
- ⚡ Response caching

**Stack:** FastAPI + Ollama (Mistral/TinyLlama) + React + FAISS + sentence-transformers

---

## 📁 Project Structure

```
Tamil_AI/
├── backend/
│   ├── main.py              # FastAPI entry point
│   ├── config.py            # Centralised settings
│   ├── requirements.txt
│   ├── .env.example
│   ├── routes/
│   │   ├── chat.py          # POST /api/chat
│   │   ├── upload.py        # POST /api/upload
│   │   ├── rag.py           # POST /api/rag/query
│   │   └── admin.py         # /api/admin/*
│   ├── services/
│   │   ├── cache_service.py # LRU + TTL cache
│   │   └── upload_service.py
│   ├── ai/
│   │   ├── ollama_client.py # Async Ollama HTTP client
│   │   ├── intent_engine.py # Keyword + LLM intent classifier
│   │   ├── rag_engine.py    # FAISS RAG pipeline
│   │   ├── memory_system.py # Session conversation memory
│   │   └── orchestrator.py  # Core brain — routes all requests
│   ├── tools/
│   │   ├── tool_engine.py   # Intent → tool dispatcher
│   │   ├── summarizer.py
│   │   ├── calculator.py    # AST-safe expression evaluator
│   │   ├── translator.py
│   │   └── file_reader.py
│   └── tests/
│       └── test_system.py
├── frontend/
│   ├── public/index.html
│   └── src/
│       ├── App.js
│       ├── index.css        # Full design system
│       ├── index.js
│       ├── components/
│       │   ├── ChatView.jsx
│       │   └── AdminView.jsx
│       └── services/
│           └── api.js
├── setup.ps1                # Windows setup script
└── README.md
```

---

## 🚀 Quick Start

### Step 1: Install Ollama

```powershell
# Download from https://ollama.com/download and install
# Then pull a lightweight model:
ollama pull mistral         # ~4GB, recommended
# OR
ollama pull tinyllama       # ~637MB, fastest on CPU
```

### Step 2: Start Ollama

```powershell
ollama serve
# Verify: http://localhost:11434
```

### Step 3: Backend Setup

```powershell
cd backend

# Create virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
copy .env.example .env
# Edit .env if needed (change OLLAMA_MODEL=tinyllama for faster responses)

# Start server
python main.py
# API docs: http://localhost:8000/docs
```

### Step 4: Frontend Setup

```powershell
cd frontend
npm install
npm start
# Open: http://localhost:3000
```

---

## 🧪 Run Tests

```powershell
cd backend
.\venv\Scripts\activate
pytest -v
```

---

## 🔌 API Reference

| Method | Endpoint              | Description                     |
|--------|-----------------------|---------------------------------|
| POST   | /api/chat             | Send a chat message             |
| POST   | /api/upload           | Upload a document (PDF/DOCX/TXT)|
| GET    | /api/files            | List uploaded files             |
| DELETE | /api/files/{name}     | Delete a file                   |
| POST   | /api/rag/query        | Query the knowledge base        |
| GET    | /api/rag/stats        | RAG index statistics            |
| POST   | /api/rag/reset        | Clear the RAG index             |
| GET    | /api/admin/status     | Full system status              |
| POST   | /api/admin/retrain    | Re-index all uploaded files     |
| POST   | /api/admin/clear-memory | Purge session memories        |
| POST   | /api/admin/clear-cache  | Clear LLM response cache      |
| GET    | /health               | Health check                    |

---

## ⚡ CPU Optimization Notes

| Optimization | Detail |
|---|---|
| Small context window | `num_ctx=2048` reduces LLM memory usage |
| Thread limit | `num_thread=4` matches typical CPU core count |
| Response cache | LRU+TTL cache avoids duplicate LLM calls |
| Keyword fast-path | Intent detection skips LLM for obvious queries |
| Lazy embedding load | MiniLM model loads only when first file is uploaded |
| Async I/O | File parsing runs in thread executor, non-blocking |
| Token trimming | Summarizer/file-reader trim inputs to ≤600 words |

---

## 🤖 Supported Intents

| Intent | Trigger Example |
|---|---|
| `chat` | "What is AI?" / "வணக்கம்" |
| `summarize` | "Summarize: [text]" / "சுருக்கம்" |
| `calculate` | "Calculate 25 * 48" / "2^10" |
| `translate` | "Translate 'good morning' to Tamil" |
| `search_rag` | "Find in document: history of Tamil" |
| `file_read` | "Read the uploaded file" |
