import { useRealtime } from "../hooks/useRealtime";
import { apiService } from "../services/api";
import { Activity, Server, Database } from "lucide-react";
import type { ComponentType } from "react";

function MetricBar({ value, label, color = "bg-blue-500" }: { value: number; label: string; color?: string }) {
  const pct = Math.min(value, 100);
  const isWarning = pct > 70;
  const isDanger = pct > 90;
  const barColor = isDanger ? "bg-red-500" : isWarning ? "bg-amber-500" : color;

  return (
    <div className="space-y-1.5">
      <div className="flex justify-between text-sm">
        <span className="text-slate-600 dark:text-slate-400">{label}</span>
        <span className={`font-semibold ${isDanger ? "text-red-500" : isWarning ? "text-amber-500" : "text-slate-800 dark:text-slate-200"}`}>
          {pct.toFixed(1)}%
        </span>
      </div>
      <div className="h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-500 ${barColor}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function StatCard({ label, value, icon: Icon, desc }: { label: string; value: string | number; icon: ComponentType<{ size?: number; className?: string }>; desc?: string }) {
  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 p-5 shadow-sm">
      <div className="flex items-center gap-3 mb-3">
        <div className="p-2 rounded-lg bg-blue-500/10">
          <Icon size={18} className="text-blue-500" />
        </div>
        <span className="text-sm font-medium text-slate-600 dark:text-slate-400">{label}</span>
      </div>
      <div className="text-2xl font-bold">{value}</div>
      {desc && <p className="text-xs text-slate-400 mt-1">{desc}</p>}
    </div>
  );
}

export function Health() {
  const { data: health, loading, error } = useRealtime(
    apiService.getSystemHealth,
    5000
  );

  if (loading && !health) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-32 bg-slate-200 dark:bg-slate-800 rounded-xl animate-pulse" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-red-500 text-sm p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">
        Error loading system health: {error.message}
      </div>
    );
  }

  if (!health) return null;

  const uptimeHours = health.vps ? (health.vps.uptime_seconds / 3600).toFixed(1) : "—";

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">System Health</h2>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          Real-time monitoring for your VPS, agents, and command queue.
        </p>
      </div>

      {/* Queue Health */}
      <section>
        <h3 className="text-base font-semibold mb-3 flex items-center gap-2">
          <Database size={16} className="text-blue-500" /> Queue Health
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <StatCard label="Pending" value={health.queue?.pending ?? 0} icon={Activity} desc="Awaiting agent pickup" />
          <StatCard label="Failed" value={health.queue?.failed ?? 0} icon={Activity} desc="Commands that errored" />
          <StatCard label="Completed" value={health.queue?.completed ?? 0} icon={Activity} desc="Successfully executed" />
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
          <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 p-5 shadow-sm flex items-center justify-between">
            <div>
              <span className="text-sm font-medium text-slate-500 dark:text-slate-400">Average Pending Time</span>
              <div className="text-xl font-bold mt-1">
                {health.queue?.avg_wait_seconds !== undefined
                  ? health.queue.avg_wait_seconds >= 60
                    ? `${(health.queue.avg_wait_seconds / 60).toFixed(1)}m`
                    : `${health.queue.avg_wait_seconds.toFixed(1)}s`
                  : "—"}
              </div>
            </div>
            <span className="text-xs px-2.5 py-1 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
              Last 24h
            </span>
          </div>
          <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 p-5 shadow-sm flex items-center justify-between">
            <div>
              <span className="text-sm font-medium text-slate-500 dark:text-slate-400">Average Execution Time</span>
              <div className="text-xl font-bold mt-1">
                {health.queue?.avg_execution_seconds !== undefined
                  ? health.queue.avg_execution_seconds >= 60
                    ? `${(health.queue.avg_execution_seconds / 60).toFixed(1)}m`
                    : `${health.queue.avg_execution_seconds.toFixed(1)}s`
                  : "—"}
              </div>
            </div>
            <span className="text-xs px-2.5 py-1 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
              Last 24h
            </span>
          </div>
        </div>
      </section>

      {/* VPS Health */}
      <section>
        <h3 className="text-base font-semibold mb-3 flex items-center gap-2">
          <Server size={16} className="text-blue-500" /> VPS Health (Hostinger)
        </h3>
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 p-6 shadow-sm space-y-5">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <MetricBar value={health.vps?.cpu_percent ?? 0} label="CPU Usage" color="bg-blue-500" />
            <MetricBar value={health.vps?.ram_percent ?? 0} label="RAM Usage" color="bg-violet-500" />
            <MetricBar value={health.vps?.disk_percent ?? 0} label="Disk Usage" color="bg-amber-500" />
          </div>
          <div className="pt-3 border-t border-slate-100 dark:border-slate-800">
            <span className="text-sm text-slate-500 dark:text-slate-400">
              Uptime: <span className="font-medium text-slate-800 dark:text-slate-200">{uptimeHours}h</span>
            </span>
          </div>
        </div>
      </section>

      {/* Failure Tracing */}
      {health.queue?.recent_failures && health.queue.recent_failures.length > 0 && (
        <section>
          <h3 className="text-base font-semibold mb-3 flex items-center gap-2 text-red-500">
            <Activity size={16} /> Recent Queue Failures
          </h3>
          <div className="rounded-xl border border-red-200 dark:border-red-900/30 bg-red-50/20 dark:bg-red-950/10 p-5 shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm border-collapse">
                <thead>
                  <tr className="border-b border-red-200/50 dark:border-red-900/20 text-xs font-semibold text-slate-500 uppercase">
                    <th className="pb-2">Command ID</th>
                    <th className="pb-2">Tool</th>
                    <th className="pb-2">Input</th>
                    <th className="pb-2 text-red-600 dark:text-red-400">Error Message</th>
                    <th className="pb-2">Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-red-200/20 dark:divide-red-900/10">
                  {health.queue.recent_failures.map((fail) => (
                    <tr key={fail.command_id} className="text-xs text-slate-700 dark:text-slate-300">
                      <td className="py-2.5 font-mono text-slate-400">{fail.command_id.slice(0, 8)}...</td>
                      <td className="py-2.5 font-medium">{fail.tool}</td>
                      <td className="py-2.5 max-w-[200px] truncate text-slate-500" title={fail.input}>{fail.input}</td>
                      <td className="py-2.5 text-red-600 dark:text-red-400 max-w-[300px] truncate" title={fail.error}>{fail.error}</td>
                      <td className="py-2.5 text-slate-400">{new Date(fail.time + "Z").toLocaleTimeString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
