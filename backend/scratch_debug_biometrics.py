print("1. Importing sys and os...")
import sys
import os
from pathlib import Path

print("2. Current working directory:", os.getcwd())

# Add agent path
agent_path = str(Path(__file__).parent / "agent")
print("Agent path calculated as:", agent_path)
# Wait, parent of H:\AI_LLM\Tamil_AI\backend\scratch_debug_biometrics.py is H:\AI_LLM\Tamil_AI\backend.
# So agent path should be Path(__file__).parent.parent / "agent"
agent_path_correct = str(Path(__file__).parent.parent / "agent")
print("Correct agent path calculated as:", agent_path_correct)

if agent_path_correct not in sys.path:
    sys.path.append(agent_path_correct)

print("3. Importing speaker_verifier...")
from voice.speaker_verifier import enrollment_calibration, extract_mfcc_features, cosine_similarity
print("Imported speaker verifier successfully!")

print("4. Importing security...")
from security.voice_security import sign_embedding, verify_signature, get_voice_secret
print("Imported security successfully!")

print("5. Importing models...")
from models.base import db_manager
from models.voice_profile import VoiceProfileModel, VoiceAuthLogModel, VoiceLockoutModel
print("Imported models successfully!")

print("6. Mocking calibration run...")
import io
import wave
import math

def create_dummy_wav(duration_sec=0.5, amplitude=1000) -> bytes:
    out = io.BytesIO()
    with wave.open(out, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        num_samples = int(16000 * duration_sec)
        samples = []
        for i in range(num_samples):
            val = int(amplitude * math.sin(2 * math.pi * 440 * i / 16000))
            samples.append(val)
        import struct
        data = struct.pack('<' + 'h' * num_samples, *samples)
        wf.writeframes(data)
    return out.getvalue()

s1 = create_dummy_wav(0.5, 1000)
s2 = create_dummy_wav(0.5, 1200)
s3 = create_dummy_wav(0.5, 900)

print("7. Running enrollment calibration...")
res = enrollment_calibration([s1, s2, s3])
print("Calibration result:", res.keys())
print("Adaptive threshold:", res["adaptive_threshold"])
print("Confirm threshold:", res["confirm_threshold"])
print("Embedding length:", len(res["embedding_vector"]))

print("ALL OPERATIONS COMPLETED SUCCESSFULLY WITH NO HANGS!")
