import { useRealtime } from "../hooks/useRealtime";
import { apiService } from "../services/api";
import { Activity, Clock, Server, TerminalSquare, AlertCircle, CheckCircle2, FileCode2, MonitorSmartphone } from "lucide-react";
import { format } from "date-fns";

export function Overview() {
  const { data: metrics, loading, error } = useRealtime(
    apiService.getDashboardMetrics,
    10000 // 10s polling as requested for Overview
  );

  if (loading && !metrics) return <div className="animate-pulse flex gap-4"><div className="h-32 w-full bg-slate-200 dark:bg-slate-800 rounded-xl"></div></div>;
  if (error) return <div className="text-red-500 bg-red-100 p-4 rounded-md">Error loading metrics: {error.message}</div>;
  if (!metrics) return null;

  const statCards = [
    { title: "Total Commands", value: metrics.total_commands, icon: TerminalSquare, color: "text-blue-500", bg: "bg-blue-500/10" },
    { title: "Success Rate", value: `${metrics.success_rate_percent}%`, icon: CheckCircle2, color: "text-emerald-500", bg: "bg-emerald-500/10" },
    { title: "Failed Commands", value: metrics.failed_commands, icon: AlertCircle, color: "text-red-500", bg: "bg-red-500/10" },
    { title: "Pending Queue", value: metrics.pending_commands, icon: Clock, color: "text-amber-500", bg: "bg-amber-500/10" },
    { title: "Avg Runtime", value: `${metrics.avg_execution_time_ms}ms`, icon: Activity, color: "text-indigo-500", bg: "bg-indigo-500/10" },
    { title: "Online Devices", value: metrics.online_devices, icon: Server, color: "text-emerald-500", bg: "bg-emerald-500/10" },
    { title: "Offline Devices", value: metrics.offline_devices, icon: Server, color: "text-slate-500", bg: "bg-slate-500/10" },
    { title: "Commands Today", value: metrics.commands_today, icon: Activity, color: "text-violet-500", bg: "bg-violet-500/10" },
    { title: "Most Used Tool", value: metrics.most_used_tool, icon: FileCode2, color: "text-cyan-500", bg: "bg-cyan-500/10" },
    { title: "Last Active", value: metrics.last_active_device, icon: MonitorSmartphone, color: "text-fuchsia-500", bg: "bg-fuchsia-500/10" },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Platform Overview</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">Live metrics from your AI agents and devices.</p>
        </div>
        <div className="text-xs text-slate-400">
          Last updated: {format(new Date(), "HH:mm:ss")}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5">
        {statCards.map((stat, i) => (
          <div key={i} className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 p-6 shadow-sm flex flex-col gap-2 hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-slate-500 dark:text-slate-400">{stat.title}</span>
              <div className={`p-2 rounded-md ${stat.bg} ${stat.color}`}>
                <stat.icon size={16} />
              </div>
            </div>
            <div className="text-2xl font-bold">{stat.value}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
