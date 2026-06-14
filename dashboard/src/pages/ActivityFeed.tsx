import { useRealtime } from "../hooks/useRealtime";
import { apiService } from "../services/api";
import { format } from "date-fns";
import { Activity, CheckCircle2, XCircle, Clock } from "lucide-react";
import type { Command, Execution } from "../types";

type ActivityFeedItem = Command & { execution?: Execution };

function ActivityItem({ item }: { item: ActivityFeedItem }) {
  const isSuccess = item.status === "completed";
  const isFailed = item.status === "failed";
  const isPending = item.status === "pending" || item.status === "executing";

  return (
    <div className="flex items-center gap-4 py-3 border-b border-slate-100 dark:border-slate-800 last:border-0 hover:bg-slate-50/80 dark:hover:bg-slate-800/30 px-4 transition-colors">
      {/* Status icon */}
      <div className="shrink-0">
        {isSuccess && <CheckCircle2 size={18} className="text-emerald-500" />}
        {isFailed && <XCircle size={18} className="text-red-500" />}
        {isPending && <Clock size={18} className="text-amber-500 animate-pulse" />}
      </div>

      {/* Timestamp */}
      <span className="text-xs font-mono text-slate-400 w-16 shrink-0">
        {format(new Date(item.created_at), "HH:mm:ss")}
      </span>

      {/* Command text */}
      <div className="flex-1 min-w-0">
        <p className="font-medium text-sm truncate">{item.raw_input || item.tool}</p>
        <p className="text-xs text-slate-400 font-mono">{item.tool} · {item.device_id}</p>
      </div>

      {/* Status badge */}
      <span className={`text-xs px-2 py-0.5 rounded-full font-medium shrink-0 ${
        isSuccess ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400" :
        isFailed  ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400" :
                    "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
      }`}>
        {item.status.toUpperCase()}
      </span>
    </div>
  );
}

export function ActivityFeed() {
  const { data: activity, loading, error, lastUpdated } = useRealtime(
    apiService.getLiveActivity,
    5000
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Live Activity Feed</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Real-time command execution stream across all devices. Refreshes every 5s.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="relative flex h-3 w-3">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500" />
          </span>
          <span className="text-xs text-slate-500 dark:text-slate-400">
            {lastUpdated ? `Updated ${format(lastUpdated, "HH:mm:ss")}` : "Connecting..."}
          </span>
        </div>
      </div>

      {loading && !activity && (
        <div className="space-y-2">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-14 bg-slate-200 dark:bg-slate-800 rounded-lg animate-pulse" />
          ))}
        </div>
      )}

      {error && (
        <div className="text-red-500 text-sm p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">
          Error: {error.message}
        </div>
      )}

      {!loading && !error && (!activity || activity.length === 0) && (
        <div className="text-center py-24 text-slate-500 dark:text-slate-400">
          <Activity size={48} className="mx-auto mb-4 opacity-20" />
          <p className="text-lg font-medium">No activity yet</p>
          <p className="text-sm mt-1">Issue a Tamil AI command to see it appear here in real time.</p>
        </div>
      )}

      {activity && activity.length > 0 && (
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 shadow-sm overflow-hidden">
          <div className="divide-y divide-slate-100 dark:divide-slate-800">
            {activity.map((item: ActivityFeedItem) => (
              <ActivityItem key={item.id} item={item} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
