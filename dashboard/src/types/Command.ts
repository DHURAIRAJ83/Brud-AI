export interface Command {
  id: string;
  device_id: string;
  user_id: string;
  tool: string;
  params: Record<string, unknown>;
  raw_input?: string;
  source_language?: string;
  status: "pending" | "approved" | "rejected" | "executing" | "completed" | "failed";
  trust_level: "SAFE" | "CAUTION" | "DANGEROUS";
  created_at: string;
  updated_at: string;
}
