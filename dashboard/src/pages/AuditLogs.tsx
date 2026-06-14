import { useState } from "react";
import { useRealtime } from "../hooks/useRealtime";
import { apiService } from "../services/api";
import type { AuditLog } from "../types";
import { format } from "date-fns";
import { ShieldCheck, Calendar } from "lucide-react";

type TimeFilter = "today" | "7d" | "30d" | "all";

function ResultBadge({ result }: { result: string }) {
  const styles: Record<string, string> = {
    success: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
    failure: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
    denied:  "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  };
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${styles[result] || ""}`}>
      {result.toUpperCase()}
    </span>
  );
}

export function AuditLogs() {
  const [timeFilter, setTimeFilter] = useState<TimeFilter>("all");

  const fetchFn = () => apiService.getAuditLogs(timeFilter);
  const { data: logs, loading, error } = useRealtime(fetchFn, 10000);

  const timeFilters: { label: string; value: TimeFilter }[] = [
    { label: "All Time", value: "all" },
    { label: "Today", value: "today" },
    { label: "7 Days", value: "7d" },
    { label: "30 Days", value: "30d" },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Audit Logs</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">Full security and activity audit trail for the platform.</p>
        </div>
        <div className="flex items-center gap-2">
          <Calendar size={14} className="text-slate-400" />
          {timeFilters.map(({ label, value }) => (
            <button
              key={value}
              onClick={() => setTimeFilter(value)}
              className={`text-xs px-3 py-1.5 rounded-full transition-colors ${
                timeFilter === value
                  ? "bg-blue-600 text-white"
                  : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {loading && !logs && (
        <div className="space-y-2">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-10 w-full bg-slate-200 dark:bg-slate-800 rounded-lg animate-pulse" />
          ))}
        </div>
      )}

      {error && (
        <div className="text-red-500 text-sm p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">
          Error: {error.message}
        </div>
      )}

      {!loading && !error && (!logs || logs.length === 0) && (
        <div className="text-center py-20 text-slate-500 dark:text-slate-400">
          <ShieldCheck size={40} className="mx-auto mb-4 opacity-30" />
          <p className="text-lg font-medium">No audit logs for this period</p>
        </div>
      )}

      {logs && logs.length > 0 && (
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 overflow-hidden shadow-sm">
          <table className="w-full text-sm">
            <thead className="border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900">
              <tr>
                {["Timestamp", "User", "Action", "Device", "Result"].map((h) => (
                  <th key={h} className="text-left text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide px-4 py-3">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {logs.map((log: AuditLog) => (
                <tr key={log.id} className="hover:bg-slate-50/80 dark:hover:bg-slate-800/30 transition-colors">
                  <td className="px-4 py-3 text-xs text-slate-400 font-mono whitespace-nowrap">
                    {format(new Date(log.timestamp), "HH:mm:ss dd MMM yyyy")}
                  </td>
                  <td className="px-4 py-3 text-xs font-mono text-slate-500 dark:text-slate-400">{log.user_id}</td>
                  <td className="px-4 py-3 font-medium">{log.action}</td>
                  <td className="px-4 py-3 text-xs text-slate-500 dark:text-slate-400">{log.device_id || "—"}</td>
                  <td className="px-4 py-3"><ResultBadge result={log.result} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
