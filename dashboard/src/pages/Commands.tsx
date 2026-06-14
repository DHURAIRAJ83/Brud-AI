import { useState } from "react";
import { useRealtime } from "../hooks/useRealtime";
import { apiService } from "../services/api";
import type { Command } from "../types";
import { format } from "date-fns";
import { TerminalSquare, Filter } from "lucide-react";

type StatusFilter = "all" | "completed" | "failed" | "pending" | "executing";

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    completed: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
    failed:    "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
    pending:   "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
    executing: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
    approved:  "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400",
    rejected:  "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400",
  };
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${styles[status] || styles.rejected}`}>
      {status.toUpperCase()}
    </span>
  );
}

function TrustBadge({ trust }: { trust: string }) {
  const styles: Record<string, string> = {
    SAFE:      "bg-emerald-50 text-emerald-600 border-emerald-200 dark:bg-emerald-900/20 dark:text-emerald-400 dark:border-emerald-800",
    CAUTION:   "bg-amber-50 text-amber-600 border-amber-200 dark:bg-amber-900/20 dark:text-amber-400 dark:border-amber-800",
    DANGEROUS: "bg-red-50 text-red-600 border-red-200 dark:bg-red-900/20 dark:text-red-400 dark:border-red-800",
  };
  return (
    <span className={`px-1.5 py-0.5 rounded border text-xs font-medium ${styles[trust] || ""}`}>
      {trust}
    </span>
  );
}

export function Commands() {
  const [filter, setFilter] = useState<StatusFilter>("all");

  const { data: commands, loading, error } = useRealtime(
    apiService.getCommands,
    5000
  );

  const filtered = commands
    ? filter === "all" ? commands : commands.filter((c: Command) => c.status === filter)
    : [];

  const filterButtons: StatusFilter[] = ["all", "completed", "failed", "pending", "executing"];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Command History</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">All AI commands with trust levels and execution results.</p>
        </div>
        <div className="flex items-center gap-2">
          <Filter size={14} className="text-slate-400" />
          {filterButtons.map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`text-xs px-3 py-1.5 rounded-full transition-colors ${
                filter === f
                  ? "bg-blue-600 text-white"
                  : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700"
              }`}
            >
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {loading && !commands && (
        <div className="space-y-2">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-12 w-full bg-slate-200 dark:bg-slate-800 rounded-lg animate-pulse" />
          ))}
        </div>
      )}

      {error && (
        <div className="text-red-500 text-sm p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">
          Error: {error.message}
        </div>
      )}

      {!loading && !error && filtered.length === 0 && (
        <div className="text-center py-20 text-slate-500 dark:text-slate-400">
          <TerminalSquare size={40} className="mx-auto mb-4 opacity-30" />
          <p className="text-lg font-medium">No commands found</p>
          <p className="text-sm mt-1">Commands from your AI agents will appear here.</p>
        </div>
      )}

      {filtered.length > 0 && (
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 overflow-hidden shadow-sm">
          <table className="w-full text-sm">
            <thead className="border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900">
              <tr>
                {["Timestamp", "Command (Raw Input)", "Tool", "Device", "Trust", "Status"].map((h) => (
                  <th key={h} className="text-left text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide px-4 py-3">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {filtered.map((cmd: Command) => (
                <tr key={cmd.id} className="hover:bg-slate-50/80 dark:hover:bg-slate-800/30 transition-colors">
                  <td className="px-4 py-3 text-xs text-slate-400 font-mono whitespace-nowrap">
                    {format(new Date(cmd.created_at), "HH:mm:ss dd MMM")}
                  </td>
                  <td className="px-4 py-3">
                    <span className="font-medium">{cmd.raw_input || "—"}</span>
                    {cmd.source_language && (
                      <span className="ml-2 text-xs text-slate-400">[{cmd.source_language}]</span>
                    )}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-blue-600 dark:text-blue-400">{cmd.tool}</td>
                  <td className="px-4 py-3 text-xs text-slate-500 dark:text-slate-400">{cmd.device_id}</td>
                  <td className="px-4 py-3"><TrustBadge trust={cmd.trust_level} /></td>
                  <td className="px-4 py-3"><StatusBadge status={cmd.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
