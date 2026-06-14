# Rudran AI - Administration Guide

The Rudran Ops Dashboard provides a centralized GUI for managing the entire AI platform.

## 1. Hybrid AI Runtime

Navigate to the **Health** tab to monitor the AI Runtime.
Rudran AI uses a Hybrid failover system. You can configure:
- **Local Mode:** Force the system to use local Ollama.
- **Cloud Mode:** Force the system to use VPS/Cloud Ollama.
- **Hybrid Mode (Recommended):** The system routes requests locally to save costs, but auto-fails over to the Cloud if the local system is overwhelmed or offline.

## 2. Model Fine-Tuning Wizard

The Fine-Tuning Wizard allows you to curate instruction-tuning datasets directly from user chat history.
1. Open the **Models** tab.
2. Select high-quality chat logs.
3. Click "Generate Dataset" to export a `.jsonl` file.
4. Click "Create Modelfile" to wrap the dataset into an Ollama Modelfile.
5. The backend will automatically execute `ollama create rudran-custom -f Modelfile`.

## 3. Managing Users and Memory

Navigate to the **Audit Logs** to view system activity.
In the backend, SQLite memory files (`memory.db` and `agent.db`) manage persistent context. The Admin can clear expired sessions from the Ops Dashboard to free up disk space.

## 4. Troubleshooting Device Connectivity

If an agent (Desktop/Android) appears as `OFFLINE` on the **Devices** tab:
- Ensure the agent is running and has the correct `BACKEND_URL` in its `.env` file.
- Verify that `SECURITY_ENABLED=True` hasn't invalidated the agent's API key. You may need to delete the device and re-register it.
