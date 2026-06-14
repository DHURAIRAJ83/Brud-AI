# Rudran AI - Desktop & Android Agent Setup

Rudran AI operates on a Hub-and-Spoke model where the central FastAPI backend manages multiple peripheral "Agents" (Desktop, Android, VPS). These agents poll the Command Queue and execute tasks locally.

## 1. Desktop Agent Initialization

1. Open a terminal in the `desktop/` directory.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and configure the backend URL:
   ```env
   BACKEND_URL=http://localhost:8000
   DEVICE_NAME=My_Windows_PC
   ```
4. Run the agent:
   ```bash
   python agent.py
   ```
5. On the first run, the agent will call `POST /api/v1/devices/register` and save its generated `X-API-Key` locally.
6. The agent will now begin sending heartbeat pings every 30 seconds and polling for queued commands.

## 2. Managing Agents via Dashboard

- Open the Ops Dashboard and navigate to the **Devices** tab.
- You will see your active Desktop Agent marked as `ONLINE`.
- You can manually push commands (e.g., `take_screenshot`, `open_browser`) from the **Commands** tab targeting the specific Device ID.

## 3. Android Agent (Roadmap Phase 6D)

*Note: Android agent support is currently under development.*
When released, the Android agent will function similarly, registering via the same REST API and executing mobile-specific commands (e.g., `read_sms`, `get_location`).
