export interface AuditLog {
  id: string;
  user_id: string;
  device_id?: string;
  action: string;
  details?: Record<string, unknown>;
  result: "success" | "failure" | "denied";
  timestamp: string;
}
