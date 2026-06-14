export interface VoiceMetrics {
  total_sessions: number;
  average_confidence: number;
  failed_sessions: number;
  wakeword_hits: number;
  confirmation_requests: number;
  rejected_commands: number;
  interrupted_commands: number;
}
