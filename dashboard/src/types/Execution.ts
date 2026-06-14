export interface Execution {
  id: string;
  command_id: string;
  device_id: string;
  status: "started" | "success" | "error";
  result_data?: Record<string, unknown>;
  error_message?: string;
  duration_ms?: number;
  started_at: string;
  completed_at?: string;
}
