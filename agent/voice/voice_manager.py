import io
import os
import wave
import time
import uuid
import logging
import threading
import httpx
import hashlib
import json
import asyncio
import websockets
from typing import Optional
# Unshadow config module import for agent
import os
import importlib.util

def _get_agent_settings():
    try:
        from config import get_settings
        s = get_settings()
        if hasattr(s, "user_id"):
            return s
    except Exception:
        pass
    try:
        agent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        config_path = os.path.join(agent_dir, "config.py")
        spec = importlib.util.spec_from_file_location("agent_config", config_path)
        agent_config = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(agent_config)
        return agent_config.get_settings()
    except Exception:
        class MockSettings:
            vps_url = "http://localhost:8000"
            user_id = "admin-user-123"
        return MockSettings()

settings = _get_agent_settings()
from voice.tts import tts_player
from voice.stt import stt_transcriber
from voice.wakeword import WakeWordDetector

logger = logging.getLogger(__name__)



class VoiceManager:
    def __init__(self):
        self.state = "sleep"  # sleep, listening, confirming, executing
        self.session_active = False
        self.last_activity_time = 0.0
        self.active_session_id = None
        self.voice_context = {
            "active_file": "main.py",
            "active_project": "Tamil_AI",
            "active_skill": "assistant"
        }
        
        # Threads and listeners
        self.wakeword_detector = None
        self._timeout_thread = None
        self._ws_thread = None
        self._running = False
        
        # PTT trigger status
        self._ptt_pressed = False

    def start(self):
        """Starts the Voice OS manager and listener threads."""
        self._running = True
        
        # Initialize wake word detector
        self.wakeword_detector = WakeWordDetector(callback=self._on_wakeword_trigger)
        self.wakeword_detector.start()
        
        # Setup PTT key hook
        self._setup_ptt_listener()
        
        # Start session inactivity timeout checker thread
        self._timeout_thread = threading.Thread(target=self._check_session_timeout_loop, daemon=True)
        self._timeout_thread.start()

        # Start WebSocket system-events listener
        self._start_system_events_listener()
        
        logger.info("Tamil AI Voice OS Manager initialized in mode: %s", settings.voice_trigger_mode)

    def _start_system_events_listener(self):
        """Start the WebSocket listener thread if not already running."""
        if self._ws_thread is None or not self._ws_thread.is_alive():
            self._ws_thread = threading.Thread(target=self._run_ws_listener_loop, daemon=True)
            self._ws_thread.start()
            logger.info("System events WebSocket listener thread started.")

    def stop(self):
        """Stops all background processes."""
        self._running = False
        if self.wakeword_detector:
            self.wakeword_detector.stop()
        logger.info("Tamil AI Voice OS Manager stopped.")

    def _setup_ptt_listener(self):
        """Setup global keyboard hook for CTRL+SPACE PTT trigger."""
        if settings.voice_trigger_mode != "push_to_talk":
            return
            
        try:
            import keyboard
            logger.info("Registering PTT key shortcut: CTRL + SPACE")
            keyboard.add_hotkey("ctrl+space", self._on_ptt_pressed)
        except Exception as e:
            logger.warning("Could not register PTT keyboard hotkey: %s. PTT can be triggered via tests.", e)

    def _on_ptt_pressed(self):
        """Called when PTT hotkey triggers."""
        logger.info("PTT triggered via hotkey!")
        # Run trigger voice session in background
        threading.Thread(target=self._trigger_voice_session, args=("PTT Key",), daemon=True).start()

    def _on_wakeword_trigger(self, wakeword: str):
        """Called when OpenWakeWord triggers."""
        logger.info("Wake word triggered: %s", wakeword)
        threading.Thread(target=self._trigger_voice_session, args=(wakeword,), daemon=True).start()

    def _check_session_timeout_loop(self):
        """Background thread checking if active session has timed out due to inactivity."""
        while self._running:
            if self.session_active:
                elapsed = time.time() - self.last_activity_time
                if elapsed > settings.voice_session_timeout:
                    logger.info("Voice Session timed out after %.1fs of inactivity. Returning to sleep.", elapsed)
                    self.session_active = False
                    self.state = "sleep"
                    self.active_session_id = None
            time.sleep(1.0)

    def _trigger_voice_session(self, trigger_source: str):
        """Launches transcription, intent matching, confirmation and execution."""
        # Stop any active speaking output immediately on trigger
        tts_player.interrupt()
        
        self.last_activity_time = time.time()
        self.state = "listening"
        
        if not self.session_active:
            self.session_active = True
            self.active_session_id = str(uuid.uuid4())
            logger.info("Started new Continuous Voice Session: %s", self.active_session_id)
        
        # Lockout check before recording
        if self._check_lockout(settings.user_id):
            tts_player.speak("குரல் அணுகல் தற்காலிகமாக முடக்கப்பட்டுள்ளது")
            self.state = "sleep"
            return

        # 1. Record user command
        audio_bytes = self._record_audio()
        if not audio_bytes:
            logger.warning("Empty audio recording. Aborting command.")
            self.state = "sleep"
            return

        # Replay Attack check on recorded audio bytes
        audio_hash = self._compute_audio_hash(audio_bytes)
        if self._check_replay(audio_hash):
            logger.warning("Replay attack blocked for audio hash: %s", audio_hash)
            tts_player.speak("குரல் சரிபார்ப்பு தோல்வி")
            self.state = "sleep"
            return

        # Log session start metrics
        session_log_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc).isoformat()
        
        # 2. Transcribe Audio
        logger.info("Transcribing audio input...")
        stt_result = stt_transcriber.transcribe(audio_bytes, "command.wav")
        transcript = stt_result.get("text", "").strip()
        confidence = stt_result.get("confidence", 0.0)
        source_stt = stt_result.get("source", "unknown")
        
        logger.info("Transcribed: '%s' (confidence: %.2f from %s)", transcript, confidence, source_stt)
        
        # Reset last activity time on valid speech detection
        self.last_activity_time = time.time()

        if not transcript:
            # Low volume or failed translation
            tts_player.speak("நான் சரியாக கேட்கவில்லை. மீண்டும் சொல்ல முடியுமா?")
            self._log_session(session_log_id, started_at, trigger_source, transcript, confidence, "low_confidence", audio_bytes=audio_bytes)
            return

        # Intercept interrupt commands verbally: "நிறுத்து", "Stop", "Silent"
        if transcript.lower() in ("நிறுத்து", "stop", "silent", "silence", "cut"):
            logger.info("Verbal Stop/Interrupt received.")
            tts_player.interrupt()
            self._log_session(session_log_id, started_at, trigger_source, transcript, confidence, "completed", interrupted=1, audio_bytes=audio_bytes)
            return

        # 3. Context-Aware pronoun substitution
        processed_transcript = self._resolve_pronouns(transcript)

        # 4. Confirmation state logic:
        # Determine if command is dangerous or confidence is borderline (0.70 <= confidence < 0.75)
        is_risky_command = self._check_is_risky_command(processed_transcript)
        is_borderline_confidence = (0.65 <= confidence < settings.stt_confidence_threshold)
        
        confirmation_needed = is_risky_command or is_borderline_confidence
        confirmed = True
        
        if confirmation_needed:
            self.state = "confirming"
            prompt = f"நீங்கள் கூறியது: '{processed_transcript}'. சரியா? ஆம் அல்லது இல்லை என்று கூறவும்."
            logger.info("Entering confirmation state. Prompt: %s", prompt)
            tts_player.speak(prompt)
            
            # Record confirmation answer
            confirm_audio = self._record_audio(silence_timeout=1.2, max_duration=4.0)
            confirm_stt = stt_transcriber.transcribe(confirm_audio, "confirmation.wav")
            confirm_text = confirm_stt.get("text", "").lower().strip()
            logger.info("Confirmation response: '%s'", confirm_text)
            
            self.last_activity_time = time.time()
            
            # Yes options in Tamil/English/Tanglish
            yes_terms = {"ஆம்", "yes", "sari", "sariya", "correct", "ok", "aam"}
            if any(term in confirm_text for term in yes_terms):
                logger.info("Confirmation accepted by user.")
                confirmed = True
            else:
                logger.info("Confirmation rejected or not understood. Cancelling command.")
                confirmed = False
                tts_player.speak("கட்டளை ரத்து செய்யப்பட்டது.")
                self._log_session(session_log_id, started_at, trigger_source, processed_transcript, confidence, "cancelled", confirmation_required=1, audio_bytes=audio_bytes)
                self.state = "sleep"
                return

        # 5. Execution (Send Command to Backend)
        self.state = "executing"
        try:
            with httpx.Client(timeout=20.0) as client:
                headers = {"X-User-Id": settings.user_id}
                
                # Send standard execution request without session token first
                response = client.post(
                    f"{settings.vps_url}/api/chat",
                    headers=headers,
                    json={
                        "message": processed_transcript,
                        "session_id": self.active_session_id,
                        "source": "voice"
                    }
                )
                
                # Intercept 403 blocks requiring voice authentication sessions
                if response.status_code == 403:
                    try:
                        err_detail = response.json().get("detail", {})
                    except Exception:
                        err_detail = {}
                        
                    if isinstance(err_detail, dict) and err_detail.get("code") in (
                        "voice_verification_required", "challenge_required", "biometric_and_challenge_required"
                    ):
                        tool = err_detail.get("tool")
                        trust_level = err_detail.get("trust_level")
                        
                        # Trigger local verification and challenge workflow
                        auth_session_id = self._run_voice_verification_workflow(tool, trust_level, audio_bytes)
                        if auth_session_id:
                            # Retry request passing the authenticated session token
                            response = client.post(
                                f"{settings.vps_url}/api/chat",
                                headers=headers,
                                json={
                                    "message": processed_transcript,
                                    "session_id": self.active_session_id,
                                    "source": "voice",
                                    "voice_auth_session_id": auth_session_id
                                }
                            )
                        else:
                            # Verification failed or cancelled
                            self.state = "sleep"
                            return

                if response.status_code == 200:
                    data = response.json()
                    response_text = data.get("response", "")
                    logger.info("Backend response: %s", response_text)
                    
                    # Speak response
                    tts_player.speak(response_text)
                    self._log_session(session_log_id, started_at, trigger_source, processed_transcript, confidence, "completed", confirmation_required=1 if confirmation_needed else 0, audio_bytes=audio_bytes)
                else:
                    try:
                        err_data = response.json().get("detail", {})
                        if isinstance(err_data, dict):
                            err_msg = err_data.get("message", "இந்த செயல்பாடு தடுக்கப்பட்டுள்ளது.")
                        else:
                            err_msg = err_data or "இந்த செயல்பாடு தடுக்கப்பட்டுள்ளது."
                    except Exception:
                        err_msg = "சேவையகத்துடன் இணைப்பதில் பிழை ஏற்பட்டது."
                    tts_player.speak(err_msg)
                    self._log_session(session_log_id, started_at, trigger_source, processed_transcript, confidence, "error", audio_bytes=audio_bytes)
        except Exception as e:
            logger.error("Error executing command on backend: %s", e)
            tts_player.speak("சேவையகத்தை தொடர்பு கொள்ள முடியவில்லை.")
            self._log_session(session_log_id, started_at, trigger_source, processed_transcript, confidence, "error", audio_bytes=audio_bytes)

        self.state = "sleep"

    def _record_audio(self, silence_timeout=1.5, max_duration=10.0) -> Optional[bytes]:
        """Record raw audio from mic until silence is detected."""
        try:
            import pyaudio
            import numpy as np
        except ImportError:
            logger.warning("PyAudio/numpy not available. Returning simulated/dummy WAV.")
            return self._get_dummy_wav()

        try:
            p = pyaudio.PyAudio()
            mic_idx = None
            if settings.mic_device_index != "default":
                try:
                    mic_idx = int(settings.mic_device_index)
                except ValueError:
                    pass

            rate = 16000
            chunk = 1024
            
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=rate,
                input=True,
                input_device_index=mic_idx,
                frames_per_buffer=chunk
            )

            frames = []
            silent_chunks = 0
            # Root-Mean-Square threshold for silence detection
            silence_threshold = 400
            chunks_for_silence = int(silence_timeout * rate / chunk)
            max_chunks = int(max_duration * rate / chunk)

            logger.info("Microphone capturing active...")
            for _ in range(max_chunks):
                data = stream.read(chunk, exception_on_overflow=False)
                frames.append(data)
                
                audio_data = np.frombuffer(data, dtype=np.int16)
                rms = np.sqrt(np.mean(audio_data**2)) if len(audio_data) > 0 else 0
                
                if rms < silence_threshold:
                    silent_chunks += 1
                else:
                    silent_chunks = 0
                    
                if silent_chunks > chunks_for_silence and len(frames) > (rate / chunk * 0.8):  # at least 0.8s recorded
                    break
                    
            stream.stop_stream()
            stream.close()
            p.terminate()
            
            # Output WAV bytes
            out = io.BytesIO()
            wf = wave.open(out, 'wb')
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(rate)
            wf.writeframes(b''.join(frames))
            wf.close()
            
            return out.getvalue()
        except Exception as e:
            logger.error("PyAudio recording failed: %s", e)
            return self._get_dummy_wav()

    def _resolve_pronouns(self, text: str) -> str:
        """Substitute relative pronouns to context variables."""
        active_file = self.voice_context.get("active_file", "")
        active_project = self.voice_context.get("active_project", "")
        
        resolved = text
        if active_file:
            # Tamil Pronouns
            resolved = resolved.replace("அதைத் திற", f"vscode-ல் {active_file}-ஐ திற")
            resolved = resolved.replace("அதை திற", f"vscode-ல் {active_file}-ஐ திற")
            resolved = resolved.replace("இதைத் திற", f"vscode-ல் {active_file}-ஐ திற")
            resolved = resolved.replace("இதை திற", f"vscode-ல் {active_file}-ஐ திற")
            resolved = resolved.replace("அதை explain செய்", f"coding-ல் {active_file}-ஐ explain செய்")
            resolved = resolved.replace("அதை விளக்கு", f"coding-ல் {active_file}-ஐ explain செய்")
            resolved = resolved.replace("அதை test செய்", f"coding-ல் {active_file}-ஐ test run செய்")
            resolved = resolved.replace("அதில் error எங்கே", f"screen-ல் {active_file}-ல் error எங்கே")
            
            # Tanglish Pronouns
            resolved = resolved.replace("adhai thira", f"vscode-l {active_file}-ai thira")
            resolved = resolved.replace("adhai open pannu", f"vscode-l {active_file}-ai open pannu")
            resolved = resolved.replace("adhai explain pannu", f"coding-l {active_file}-ai explain pannu")
            resolved = resolved.replace("adhai explain sei", f"coding-l {active_file}-ai explain sei")
            resolved = resolved.replace("adhai test pannu", f"coding-l {active_file}-ai test pannu")
            
        if active_project:
            resolved = resolved.replace("அங்கு", active_project)
            resolved = resolved.replace("அங்கே", active_project)
            resolved = resolved.replace("angu", active_project)
            resolved = resolved.replace("ange", active_project)
            
        if resolved != text:
            logger.info("Pronoun engine resolved context: '%s' -> '%s'", text, resolved)
        return resolved

    def _check_is_risky_command(self, text: str) -> bool:
        """Identify destructive/dangerous commands requiring confirmation."""
        risky_terms = {
            "delete", "remove", "kill", "shutdown", "restart", "git push",
            "அழி", "நீக்கு", "முடி", "மூடு", "வெளியேறு"
        }
        text_lower = text.lower()
        return any(term in text_lower for term in risky_terms)

    def _get_dummy_wav(self) -> bytes:
        """Return silent WAV file."""
        out = io.BytesIO()
        wf = wave.open(out, 'wb')
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b'\x00' * 16000 * 2)  # 1 second of silence
        wf.close()
        return out.getvalue()

    def _log_session(
        self,
        log_id: str,
        started_at: str,
        trigger_source: str,
        transcript: str,
        confidence: float,
        status: str,
        confirmation_required: int = 0,
        interrupted: int = 0,
        audio_bytes: bytes = None
    ):
        """Submit session audit data to VPS backend asynchronously."""
        ended_at = datetime.now(timezone.utc).isoformat()
        
        # Simple duration calculation
        start_t = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        end_t = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
        duration_ms = (end_t - start_t).total_seconds() * 1000.0

        session_data = {
            "id": log_id,
            "session_id": self.active_session_id,
            "started_at": started_at,
            "ended_at": ended_at,
            "wakeword": trigger_source,
            "transcript": transcript,
            "confidence": confidence,
            "skill_id": self.voice_context.get("active_skill", "assistant"),
            "status": status,
            "duration_ms": duration_ms,
            "confirmation_required": confirmation_required,
            "interrupted": interrupted
        }

        # Submit in a separate thread so we don't block
        threading.Thread(
            target=self._log_session_to_backend,
            args=(session_data, audio_bytes),
            daemon=True
        ).start()

    def _log_session_to_backend(self, session_data: dict, audio_bytes: bytes = None):
        try:
            data = {k: str(v) for k, v in session_data.items() if v is not None}
            files = None
            if audio_bytes:
                files = {"audio": (f"{session_data['id']}.wav", audio_bytes, "audio/wav")}

            with httpx.Client(timeout=10.0) as client:
                resp = client.post(
                    f"{settings.vps_url}/api/voice/session",
                    data=data,
                    files=files
                )
                if resp.status_code == 200:
                    logger.info("Successfully synced voice session %s to backend.", session_data["id"])
                else:
                    logger.warning("Backend rejected session log %s: %d", session_data["id"], resp.status_code)
        except Exception as e:
            logger.error("Failed to post session audit log to backend: %s", e)


    def _check_lockout(self, user_id: str) -> bool:
        """Check user lockout status on backend."""
        try:
            with httpx.Client(timeout=5.0) as client:
                headers = {"X-User-Id": user_id}
                resp = client.get(f"{settings.vps_url}/api/voice/lockout-status", headers=headers)
                if resp.status_code == 200:
                    return resp.json().get("locked", False)
        except Exception as e:
            logger.error("Failed to fetch lockout status from backend: %s", e)
        return False

    def _check_voice_lockout(self) -> bool:
        """Fallback wrapper for _check_voice_lockout."""
        return self._check_lockout(settings.user_id)

    def _compute_audio_hash(self, pcm_bytes: bytes) -> str:
        """Compute SHA-256 hash of audio bytes."""
        return hashlib.sha256(pcm_bytes).hexdigest()

    def _check_and_store_replay(self, audio_hash: str, session_id: str) -> bool:
        try:
            with httpx.Client(timeout=5.0) as client:
                headers = {"X-User-Id": settings.user_id}
                resp = client.post(
                    f"{settings.vps_url}/api/voice/replay-check-and-store",
                    headers=headers,
                    data={"audio_hash": audio_hash, "session_id": session_id}
                )
                if resp.status_code == 200:
                    return resp.json().get("duplicate", False)
        except Exception as e:
            logger.error("Failed to run replay attack check on backend: %s", e)
        return False

    def _check_replay(self, audio_hash: str) -> bool:
        """Check replay attack for audio hash using the current active session."""
        return self._check_and_store_replay(audio_hash, self.active_session_id or str(uuid.uuid4()))

    def _get_command_trust_level(self, transcript: str) -> str:
        """Ask backend parser for the command's trust level."""
        try:
            with httpx.Client(timeout=5.0) as client:
                headers = {"X-User-Id": settings.user_id}
                resp = client.post(
                    f"{settings.vps_url}/api/voice/parse-command-trust",
                    headers=headers,
                    data={"message": transcript}
                )
                if resp.status_code == 200:
                    return resp.json().get("trust_level", "safe")
        except Exception as e:
            logger.error("Failed to parse command trust level from backend: %s", e)
        return "safe"

    def _create_auth_session(self, scope: str) -> Optional[str]:
        """Create a new voice auth session on the backend."""
        try:
            with httpx.Client(timeout=10.0) as client:
                headers = {"X-User-Id": settings.user_id}
                resp = client.post(
                    f"{settings.vps_url}/api/voice/auth-session",
                    headers=headers,
                    data={
                        "device_id": "desktop001",
                        "command_scope": scope,
                        "verification_source": "mfcc_fallback"
                    }
                )
                if resp.status_code == 200:
                    return resp.json().get("auth_session", {}).get("id")
                else:
                    logger.error("Failed to create voice auth session. Backend status: %d", resp.status_code)
        except Exception as e:
            logger.error("Connection error creating voice auth session: %s", e)
        return None

    def _run_speaker_verification(self, pcm_bytes: bytes, auth_session_id: str, trust_level: str = "caution") -> bool:
        """Run local speaker verification and post verification results to the backend."""
        from voice.profile_cache import profile_cache
        profiles = profile_cache.get_profiles()
        
        if not profiles:
            if trust_level == "dangerous":
                logger.warning("Dangerous command requested but no biometric templates are registered.")
                tts_player.speak("குரல் ப்ரொபைல் எதுவும் பதிவு செய்யப்படவில்லை. ஆபத்தான கட்டளைகளை செயல்படுத்த முடியாது.")
                return False
            else:
                logger.info("No voice profiles registered. Skipping speaker verification for caution command.")
                try:
                    with httpx.Client(timeout=10.0) as client:
                        headers = {"X-User-Id": settings.user_id}
                        client.post(
                            f"{settings.vps_url}/api/voice/auth-session/verify-speaker",
                            headers=headers,
                            data={
                                "auth_session_id": auth_session_id,
                                "confidence_score": 0.0,
                                "verification_status": "rejected"
                            }
                        )
                except Exception as e:
                    logger.error("Failed to post mock speaker verification to backend: %s", e)
                return True # Inherited skip for caution

        active_profile = profiles[0]
        from voice.speaker_verifier import verify_speaker
        verify_res = verify_speaker(pcm_bytes, active_profile)
        confidence = verify_res.get("confidence", 0.0)
        status = verify_res.get("status", "rejected")
        
        logger.info("Local speaker verification result: status=%s, confidence=%.4f", status, confidence)
        
        try:
            with httpx.Client(timeout=10.0) as client:
                headers = {"X-User-Id": settings.user_id}
                resp = client.post(
                    f"{settings.vps_url}/api/voice/auth-session/verify-speaker",
                    headers=headers,
                    data={
                        "auth_session_id": auth_session_id,
                        "confidence_score": confidence,
                        "verification_status": status
                    }
                )
                if resp.status_code == 200:
                    if status in ("authorized", "confirm"):
                        return True
                elif resp.status_code == 403:
                    tts_player.speak("குரல் அணுகல் தற்காலிகமாக முடக்கப்பட்டுள்ளது")
        except Exception as e:
            logger.error("Failed to post speaker verification to backend: %s", e)
        return False

    def _run_challenge(self, auth_session_id: str) -> bool:
        """Run liveness challenge workflow (TTS -> capture -> verify)."""
        from voice.challenge_manager import challenge_manager
        challenge = challenge_manager.generate_challenge(auth_session_id)
        if not challenge:
            logger.error("Failed to generate challenge sequence.")
            return False
            
        success = challenge_manager.verify_response(
            auth_session_id=auth_session_id,
            challenge_id=challenge["id"],
            challenge_digits=challenge["challenge_digits"],
            record_callback=lambda: self._record_audio(silence_timeout=1.2, max_duration=4.0)
        )
        
        if not success:
            logger.warning("Spoken challenge response verification failed.")
            tts_player.speak("எண்களை உறுதிப்படுத்துவது தோல்வி அடைந்தது.")
            return False
        else:
            logger.info("Spoken challenge response verification succeeded.")
            tts_player.speak("சரிபார்ப்பு வெற்றி.")
            return True

    def _run_voice_verification_workflow(self, tool: str, trust_level: str, audio_bytes: bytes) -> Optional[str]:
        """Orchestrate voice authentication session creation, speaker verification, and liveness challenges."""
        logger.info("Starting voice verification workflow for tool: %s, level: %s", tool, trust_level)
        
        auth_session_id = self._create_auth_session(tool)
        if not auth_session_id:
            return None
            
        # Biometrics
        biometric_passed = self._run_speaker_verification(audio_bytes, auth_session_id, trust_level)
        if not biometric_passed:
            return None
            
        # Liveness challenge
        challenge_required = (trust_level in ("caution", "dangerous"))
        if challenge_required:
            challenge_passed = self._run_challenge(auth_session_id)
            if not challenge_passed:
                return None
                
        return auth_session_id

        return auth_session_id

    def _run_ws_listener_loop(self):
        """Async loop runner for WebSocket events listening."""
        try:
            asyncio.run(self._listen_system_events())
        except Exception as e:
            logger.error("Error running WS listener loop: %s", e)

    async def _listen_system_events(self):
        """Connect to WebSocket channel /ws/system-events and refresh cache on updates."""
        ws_url = settings.vps_url.replace("http://", "ws://").replace("https://", "wss://")
        url = f"{ws_url}/ws/system-events"
        logger.info("Connecting to system events WS: %s", url)
        
        while self._running:
            try:
                async with websockets.connect(url) as websocket:
                    logger.info("Connected to system events WebSocket.")
                    while self._running:
                        msg_raw = await websocket.recv()
                        try:
                            msg = json.loads(msg_raw)
                            event = msg.get("event")
                            user_id = msg.get("user_id")
                            
                            logger.info("System events WebSocket received event: %s", event)
                            if event == "voice_profile_updated" and user_id == settings.user_id:
                                from voice.profile_cache import profile_cache
                                profile_cache.refresh_cache()
                            elif event == "user_changed":
                                logger.info("User changed event received: %s (%s)", msg.get("username"), user_id)
                                settings.user_id = user_id
                                from voice.profile_cache import profile_cache
                                profile_cache.clear()
                                profile_cache.refresh_cache()
                        except Exception as e:
                            logger.error("Error processing system event message: %s", e)
            except Exception as e:
                logger.warning("System events WebSocket connection failed/disconnected: %s. Reconnecting in 5s...", e)
                await asyncio.sleep(5.0)


from datetime import datetime, timezone
# Global singleton
voice_manager = VoiceManager()
