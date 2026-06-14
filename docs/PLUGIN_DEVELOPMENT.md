# Rudran AI - Plugin Development Guide

The Tool Engine in Rudran AI supports dynamic, hot-loaded Python plugins. You can develop custom tools and upload them via the Ops Dashboard without restarting the server.

## Plugin Structure

A valid plugin must define:
1. `PLUGIN_NAME`: A unique string identifier.
2. `PLUGIN_INTENTS`: A list of trigger strings.
3. `execute(message: str, **kwargs)`: An asynchronous function that performs the action.

### Example: `weather_plugin.py`

```python
import httpx

PLUGIN_NAME = "weather_api"
PLUGIN_INTENTS = ["get_weather", "check_temperature"]
PLUGIN_DESCRIPTION = "Fetches the current weather for a given city."

async def execute(message: str, **kwargs) -> str:
    # 'message' usually contains the extracted city name or query from the LLM.
    city = message.strip()
    if not city:
        return "Please provide a city name."
    
    # Example logic
    return f"The weather in {city} is sunny and 28°C."
```

## Security & Sandbox

To ensure system stability, uploaded plugins undergo an AST (Abstract Syntax Tree) validation.
- **Blocked Imports**: You cannot import `os`, `subprocess`, `pty`, or `shlex`. 
- **Blocked Functions**: Calls to `os.system`, `os.popen`, or `subprocess.run` will be rejected during upload.
- **Execution Environment**: Plugins run in the main FastAPI event loop. Do not use blocking synchronous calls like `time.sleep()` or blocking `requests.get()`. Always use `asyncio` and `httpx`.

## Uploading

1. Open the Ops Dashboard (`http://localhost:3001`).
2. Navigate to the **Plugins** tab.
3. Click **Upload Plugin** and select your `.py` file.
4. The backend will validate the syntax, sanitize the file, and hot-load the plugin into the `PluginRegistry`.
