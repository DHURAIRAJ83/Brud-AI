/**
 * Voice Recorder Hook — useVoiceRecorder
 * Records microphone audio and sends to /api/voice/transcribe-and-chat
 */
import { useState, useRef, useCallback } from 'react';

const BASE = 'http://localhost:8000';

export function useVoiceRecorder(sessionId, onResult) {
  const [recording, setRecording]   = useState(false);
  const [processing, setProcessing] = useState(false);
  const [error, setError]           = useState(null);
  const mediaRef                    = useRef(null);
  const chunksRef                   = useRef([]);

  const start = useCallback(async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' });
      chunksRef.current = [];

      mr.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      mr.onstop = async () => {
        stream.getTracks().forEach(t => t.stop());
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
        await sendAudio(blob);
      };

      mr.start();
      mediaRef.current = mr;
      setRecording(true);
    } catch (err) {
      setError('Microphone access denied. Please allow microphone permission.');
    }
  }, [sessionId]);

  const stop = useCallback(() => {
    if (mediaRef.current && recording) {
      mediaRef.current.stop();
      setRecording(false);
      setProcessing(true);
    }
  }, [recording]);

  const sendAudio = async (blob) => {
    const form = new FormData();
    form.append('audio', blob, 'recording.webm');
    if (sessionId) form.append('session_id', sessionId);

    try {
      const res = await fetch(`${BASE}/api/voice/transcribe-and-chat`, {
        method: 'POST', body: form,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Transcription failed');
      onResult?.(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setProcessing(false);
    }
  };

  return { recording, processing, error, start, stop };
}
