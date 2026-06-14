# Rudran AI - REST API Reference

The FastAPI backend exposes several core endpoints. If `SECURITY_ENABLED=True`, most endpoints require either an `Authorization: Bearer <JWT>` token or an `X-API-Key: <key>` header.

## 1. Authentication (`/api/auth`)
- `POST /api/auth/login`: Accepts `username` and `password`. Returns a JWT access token.
- `POST /api/auth/register`: Create a new user account.
- `GET /api/auth/me`: Returns the current authenticated user's profile.

## 2. Chat & Agents (`/api/chat`, `/api/agent`)
- `POST /api/chat`: Non-streaming chat endpoint.
- `POST /api/stream`: Streaming chat endpoint (Server-Sent Events).
- `POST /api/agent/task`: Initiates a multi-step agentic task loop using the Tool Engine.

## 3. RAG & Uploads (`/api/rag`, `/api/upload`)
- `POST /api/upload`: Upload a document (PDF, TXT, DOCX) for indexing. Returns a file ID.
- `POST /api/rag/query`: Query the embedded documents.

## 4. Plugins & Fine-Tuning (`/api/v1/admin/plugins`, `/api/v1/admin/finetune`)
- `GET /api/v1/admin/plugins`: List all registered tools and plugins.
- `POST /api/v1/admin/plugins/upload`: Upload a custom `.py` plugin file.
- `POST /api/v1/admin/finetune/generate`: Scrape chat history and generate an Ollama Modelfile.

## 5. Device Registry (`/api/v1/devices`)
- `POST /api/v1/devices/register`: Register a new desktop/Android agent. Returns an API Key.
- `POST /api/v1/devices/heartbeat`: Ping the server to maintain `ONLINE` status.

## 6. Command Queue (`/api/v1/commands`)
- `GET /api/v1/commands/`: List all pending and historical commands.
- `POST /api/v1/commands/push`: Add a new command for a device to execute.
- `POST /api/v1/commands/callback`: Devices report the result of an executed command here.
