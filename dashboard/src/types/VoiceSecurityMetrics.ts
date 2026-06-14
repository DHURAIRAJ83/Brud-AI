export interface VoiceSecurityMetrics {
  enrolled_profiles_count: number;
  success_rate: number;
  failure_rate: number;
  failed_attempts: number;
  lockout_count: number;
  replay_attack_count: number;
  last_verification_time: string | null;
}
