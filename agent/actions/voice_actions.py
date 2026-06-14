import logging
from actions.registry import action_registry

logger = logging.getLogger(__name__)


@action_registry.register("voice.list_devices")
async def list_devices(params: dict = None) -> dict:
    """Lists local microphone and speaker hardware indices."""
    microphones = []
    speakers = []
    
    try:
        import pyaudio
        p = pyaudio.PyAudio()
        try:
            device_count = p.get_device_count()
            for i in range(device_count):
                info = p.get_device_info_by_index(i)
                max_in = info.get("maxInputChannels", 0)
                max_out = info.get("maxOutputChannels", 0)
                name = info.get("name", f"Device {i}")
                
                # Check input (microphones)
                if max_in > 0:
                    microphones.append({"id": i, "name": name})
                # Check output (speakers)
                if max_out > 0:
                    speakers.append({"id": i, "name": name})
        finally:
            p.terminate()
    except Exception as e:
        logger.warning("PyAudio not available or failed to query: %s. Returning mock list.", e)
        # Mock values for headless/testing environments
        microphones = [
            {"id": 0, "name": "Default System Microphone (Mock)"},
            {"id": 1, "name": "USB Audio Mic (Mock)"}
        ]
        speakers = [
            {"id": 0, "name": "Default System Speaker (Mock)"}
        ]
        
    return {
        "microphones": microphones,
        "speakers": speakers
    }


@action_registry.register("voice.stop_speaking")
async def stop_speaking(params: dict = None) -> dict:
    """Interrupts active TTS speech output."""
    logger.info("Interrupting speech output...")
    try:
        from voice.tts import tts_player
        tts_player.interrupt()
        return {"success": True, "message": "Speech interrupted successfully"}
    except Exception as e:
        logger.error("Failed to interrupt tts player: %s", e)
        return {"success": False, "error": str(e)}
