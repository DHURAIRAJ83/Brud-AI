export interface VoiceAttempt {
  id: string;
  created_at: string;
  username?: string;
  user_id: string;
  confidence_score: number | null;
  challenge_required?: boolean;
  verification_status: string;
}
