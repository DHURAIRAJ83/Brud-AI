export interface Device {
  id: string;
  user_id: string;
  device_name: string;
  device_type: string;
  os_version?: string;
  agent_version: string;
  capabilities: string[];
  status: "online" | "offline" | "error";
  computed_status?: "ONLINE" | "OFFLINE";
  last_ip?: string;
  last_heartbeat?: string;
  registered_at: string;
}
