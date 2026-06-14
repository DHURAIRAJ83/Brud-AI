import type { Device, Command, Execution, AuditLog, DashboardMetrics, SystemHealth, VoiceSession, VoiceAttempt, VoiceMetrics, VoiceSecurityMetrics } from "../types";

// Base API URL config
// The proxy will handle requests starting with /api
const API_BASE = "/api/v1";

// Custom error for API failures
export class APIError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "APIError";
  }
}

async function fetchWithHandler<T>(url: string, options?: RequestInit): Promise<T> {
  const apiKey = import.meta.env.VITE_API_KEY || "";
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": apiKey,
      ...options?.headers,
    },
  });

  if (!res.ok) {
    throw new APIError(res.status, await res.text() || res.statusText);
  }

  return res.json();
}

export const apiService = {
  // ── Metrics & Health ──────────────────────────────────────────────
  getDashboardMetrics: () => 
    fetchWithHandler<DashboardMetrics>(`${API_BASE}/admin/dashboard/metrics`),

  getSystemHealth: () => 
    fetchWithHandler<SystemHealth>(`${API_BASE}/admin/system/health`),

  // ── Devices ───────────────────────────────────────────────────────
  getDevices: () => 
    fetchWithHandler<Device[]>(`${API_BASE}/devices`),

  getDeviceStatus: () => 
    fetchWithHandler<Device[]>(`${API_BASE}/devices/status`),

  // ── Commands & Executions ─────────────────────────────────────────
  getCommands: () => 
    fetchWithHandler<Command[]>(`${API_BASE}/commands/`),
    
  getLiveActivity: () => 
    fetchWithHandler<(Command & { execution?: Execution })[]>(`${API_BASE}/commands/activity`),

  // ── Audit Logs ────────────────────────────────────────────────────
  getAuditLogs: (filter: "today" | "7d" | "30d" | "all" = "all") => 
    fetchWithHandler<AuditLog[]>(`${API_BASE}/audit/?filter=${filter}`),

  // ── Voice OS ──────────────────────────────────────────────────────
  getVoiceSessions: () =>
    fetchWithHandler<{ sessions: VoiceSession[] }>("/api/voice/sessions"),
    
  getVoiceMetrics: () =>
    fetchWithHandler<VoiceMetrics>("/api/voice/metrics"),

  getVoiceSecurityMetrics: () =>
    fetchWithHandler<VoiceSecurityMetrics>("/api/voice/security/metrics"),

  getVoiceAttempts: (limit?: number, offset?: number) =>
    fetchWithHandler<{
      attempts: VoiceAttempt[];
    }>(`/api/voice/attempts?limit=${limit || 50}&offset=${offset || 0}`),
};
