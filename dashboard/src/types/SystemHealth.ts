export interface SystemHealth {
  queue: {
    pending: number;
    failed: number;
    completed: number;
    avg_wait_seconds?: number;
    avg_execution_seconds?: number;
    recent_failures?: {
      command_id: string;
      tool: string;
      input: string;
      error: string;
      time: string;
    }[];
  };
  vps: {
    cpu_percent: number;
    ram_percent: number;
    disk_percent: number;
    uptime_seconds: number;
  };
}
