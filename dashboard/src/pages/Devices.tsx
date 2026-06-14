import { useRealtime } from "../hooks/useRealtime";
import { apiService } from "../services/api";
import type { Device } from "../types";
import { format, formatDistanceToNow } from "date-fns";
import { Server, Wifi, WifiOff, Info } from "lucide-react";

function StatusBadge({ status }: { status: string }) {
  const isOnline = status === "ONLINE";
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium
      ${isOnline ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400"
                 : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400"}`}>
      {isOnline ? <Wifi size={12} /> : <WifiOff size={12} />}
      {status}
    </span>
  );
}

function CapabilityPills({ caps }: { caps: string[] }) {
  return (
    <div className="flex flex-wrap gap-1">
      {caps.map((cap) => (
        <span key={cap} className="px-1.5 py-0.5 text-xs rounded bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 font-mono">
          {cap}
        </span>
      ))}
    </div>
  );
}

export function Devices() {
  const { data: devices, loading, error } = useRealtime(
    apiService.getDeviceStatus,
    10000
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Device Management</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            All registered agents. Online status uses 60s heartbeat threshold.
          </p>
        </div>
        <span className="text-xs text-slate-400">Refreshes every 10s</span>
      </div>

      {loading && !devices && (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 w-full bg-slate-200 dark:bg-slate-800 rounded-lg animate-pulse" />
          ))}
        </div>
      )}

      {error && (
        <div className="flex items-center gap-3 p-4 rounded-lg bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 border border-red-200 dark:border-red-800">
          <Info size={16} />
          <span className="text-sm">Error loading devices: {error.message}</span>
        </div>
      )}

      {!loading && !error && (!devices || devices.length === 0) && (
        <div className="text-center py-20 text-slate-500 dark:text-slate-400">
          <Server size={40} className="mx-auto mb-4 opacity-30" />
          <p className="text-lg font-medium">No devices registered yet</p>
          <p className="text-sm mt-1">Start your Desktop Agent to see it appear here.</p>
        </div>
      )}

      {devices && devices.length > 0 && (
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 overflow-hidden shadow-sm">
          <table className="w-full text-sm">
            <thead className="border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900">
              <tr>
                {["Device Name", "Type / OS", "Status", "Agent Version", "Capabilities", "Last Heartbeat", "Registered", "Actions"].map((h) => (
                  <th key={h} className="text-left text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide px-4 py-3">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {devices.map((device: Device) => (
                <tr key={device.id} className="hover:bg-slate-50/80 dark:hover:bg-slate-800/30 transition-colors">
                  <td className="px-4 py-3 font-medium">{device.device_name}</td>
                  <td className="px-4 py-3 text-slate-500 dark:text-slate-400">
                    <div>{device.device_type}</div>
                    <div className="text-xs">{device.os_version || "—"}</div>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={device.computed_status || (device.status === "online" ? "ONLINE" : "OFFLINE")} />
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-500 dark:text-slate-400">{device.agent_version}</td>
                  <td className="px-4 py-3 max-w-xs">
                    <CapabilityPills caps={device.capabilities || []} />
                  </td>
                  <td className="px-4 py-3 text-slate-500 dark:text-slate-400 text-xs">
                    {device.last_heartbeat
                      ? formatDistanceToNow(new Date(device.last_heartbeat), { addSuffix: true })
                      : "Never"}
                  </td>
                  <td className="px-4 py-3 text-slate-500 dark:text-slate-400 text-xs">
                    {format(new Date(device.registered_at), "dd MMM yyyy")}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-2">
                      <button className="text-xs px-2 py-1 rounded border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors">View</button>
                      <button className="text-xs px-2 py-1 rounded border border-amber-200 dark:border-amber-800 text-amber-700 dark:text-amber-400 hover:bg-amber-50 dark:hover:bg-amber-900/20 transition-colors">Disable</button>
                      <button className="text-xs px-2 py-1 rounded border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors">Remove</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
