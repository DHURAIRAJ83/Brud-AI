import time
import logging
import threading
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class WakeWordDetector:
    def __init__(self, callback):
        self.callback = callback
        self._running = False
        self._thread = None
        self.last_trigger_time = 0.0

    def start(self):
        if not settings.wakeword_enabled:
            logger.info("Wake Word detection is disabled.")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            try:
                self._thread.join(timeout=1.0)
            except Exception:
                pass

    def _run_loop(self):
        logger.info("Starting Wake Word detector thread...")
        try:
            import pyaudio
            import numpy as np
            from openwakeword.model import Model

            # Load openwakeword models (hey_mycroft as default test model)
            model = Model(wakeword_models=["hey_mycroft"])
            
            p = pyaudio.PyAudio()
            mic_idx = None
            if settings.mic_device_index != "default":
                try:
                    mic_idx = int(settings.mic_device_index)
                except ValueError:
                    pass

            # Open 16kHz mono audio input stream for openwakeword
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                input_device_index=mic_idx,
                frames_per_buffer=1280
            )

            logger.info("✅ Wake Word microphone stream opened.")

            while self._running:
                data = stream.read(1280, exception_on_overflow=False)
                if len(data) == 0:
                    continue

                audio_data = np.frombuffer(data, dtype=np.int16)
                prediction = model.predict(audio_data)
                
                for name, confidence in prediction.items():
                    if confidence > 0.6:  # Threshold
                        now = time.time()
                        if now - self.last_trigger_time > settings.wakeword_cooldown:
                            logger.info("Wake word detected! Confidence: %.2f", confidence)
                            self.last_trigger_time = now
                            self.callback(wakeword="Hey Rudran")
                            
            stream.stop_stream()
            stream.close()
            p.terminate()

        except Exception as e:
            logger.warning("Wake word detection PyAudio/openwakeword failed: %s. Entering simulated trigger loop...", e)
            self._run_simulation_loop()

    def _run_simulation_loop(self):
        """Mock/Simulated trigger loop for testing and headless runs."""
        logger.info("Wake Word simulation loop running. Wake Word callback can be triggered manually in tests.")
        while self._running:
            time.sleep(1.0)
