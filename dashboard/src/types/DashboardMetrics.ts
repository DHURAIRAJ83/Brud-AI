export interface DashboardMetrics {
  total_commands: number;
  failed_commands: number;
  success_rate_percent: number;
  avg_execution_time_ms: number;
  online_devices: number;
  offline_devices: number;
  pending_commands: number;
  commands_today: number;
  most_used_tool: string;
  last_active_device: string;
}
