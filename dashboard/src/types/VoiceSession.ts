export interface VoiceSession {
  id: string;
  created_at: string;
  wakeword?: string;
  transcript?: string;
  confidence: number | null;
  skill_id?: string;
  duration_ms?: number;
  confirmation_required?: number;
  interrupted?: number;
  status?: string;
  audio_file?: string;
}
