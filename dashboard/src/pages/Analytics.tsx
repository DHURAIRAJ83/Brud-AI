import { useEffect, useState } from "react";
import { BarChart2, Zap, TrendingUp, PieChart, Activity } from "lucide-react";

const API = "/api";

async function apiFetch(path: string) {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

interface TokenMetrics {
  total_tokens: number;
  days: {
    date: string;
    tokens: number;
    requests: number;
    cost_usd: number;
  }[];
}

interface LatencyMetrics {
  latency_by_model: Record<string, {
    count: number;
    p50: number;
    p95: number;
    p99: number;
  }>;
}

interface IntentMetric {
  intent: string;
  pct: number;
  count: number;
}

interface IntentBreakdown {
  intents: IntentMetric[];
}

interface SystemMetrics {
  system: {
    total_requests: number;
    avg_latency_ms: number;
    cache_hit_rate_pct: number;
  };
}

// ── Simple bar chart using SVG ────────────────────────────────────────────────
function BarChart({ data, valueKey, labelKey, color = "#6366f1" }: {
  data: Record<string, string | number>[];
  valueKey: string;
  labelKey: string;
  color?: string;
}) {
  if (!data || data.length === 0) return <div className="text-sm text-slate-400 text-center py-4">No data yet</div>;
  const max = Math.max(...data.map(d => Number(d[valueKey]))) || 1;
  return (
    <div className="flex items-end gap-1 h-32 w-full">
      {data.map((d, i) => {
        const h = Math.max(4, (Number(d[valueKey]) / max) * 128);
        return (
          <div key={i} className="flex-1 flex flex-col items-center gap-1 group relative">
            <div
              className="w-full rounded-t transition-all duration-300 hover:opacity-80"
              style={{ height: h, background: color, minWidth: 4 }}
              title={`${d[labelKey]}: ${d[valueKey]}`}
            />
            <span className="text-[9px] text-slate-400 rotate-45 origin-left truncate max-w-[24px]">
              {String(d[labelKey]).slice(-5)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ── Horizontal bar (for intents) ──────────────────────────────────────────────
function HorizBar({ label, pct, count, color }: { label: string; pct: number; count: number; color: string }) {
  return (
    <div className="flex items-center gap-3 mb-2">
      <div className="w-28 text-xs text-slate-500 dark:text-slate-400 truncate">{label}</div>
      <div className="flex-1 bg-slate-100 dark:bg-slate-800 rounded-full h-2 overflow-hidden">
        <div
          className="h-2 rounded-full transition-all duration-700"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <div className="w-10 text-right text-xs text-slate-500 dark:text-slate-400">{count}</div>
    </div>
  );
}

const INTENT_COLORS: Record<string, string> = {
  chat:            "#6366f1",
  summarize:       "#22d3ee",
  calculate:       "#f59e0b",
  translate:       "#10b981",
  search_rag:      "#8b5cf6",
  file_read:       "#f97316",
  agent:           "#ec4899",
  desktop_command: "#64748b",
};

export function Analytics() {
  const [tokens, setTokens]   = useState<TokenMetrics | null>(null);
  const [latency, setLatency] = useState<LatencyMetrics | null>(null);
  const [intents, setIntents] = useState<IntentBreakdown | null>(null);
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [t, l, i, m] = await Promise.all([
          apiFetch("/metrics/tokens"),
          apiFetch("/metrics/latency"),
          apiFetch("/metrics/intents"),
          apiFetch("/metrics"),
        ]);
        setTokens(t);
        setLatency(l);
        setIntents(i);
        setMetrics(m);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    }
    load();
    const iv = setInterval(load, 30_000);
    return () => clearInterval(iv);
  }, []);

  if (loading && !tokens) return (
    <div className="flex items-center justify-center h-48 text-slate-400">
      <div className="text-center">
        <div className="animate-spin text-3xl mb-2">⚙️</div>
        Loading analytics…
      </div>
    </div>
  );

  if (error) return (
    <div className="bg-red-50 dark:bg-red-900/20 text-red-500 border border-red-200 dark:border-red-800 rounded-xl p-4">
      ⚠️ {error}
    </div>
  );

  const sys = metrics?.system;
  const totalTokens = tokens?.total_tokens || 0;
  const latencyByModel = latency?.latency_by_model || {};
  const intentList = intents?.intents || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
          <BarChart2 size={22} className="text-indigo-500" />
          Analytics Dashboard
        </h2>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          Token usage, latency, and intent breakdown — auto-refreshes every 30s
        </p>
      </div>

      {/* Top KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: "Total Requests",    value: sys?.total_requests ?? 0,                  icon: Activity,  color: "text-indigo-500", bg: "bg-indigo-500/10" },
          { label: "Total Tokens",      value: totalTokens.toLocaleString(),              icon: Zap,       color: "text-amber-500",  bg: "bg-amber-500/10" },
          { label: "Avg Latency",       value: `${sys?.avg_latency_ms?.toFixed(0) ?? 0}ms`, icon: TrendingUp, color: "text-emerald-500", bg: "bg-emerald-500/10" },
          { label: "Cache Hit Rate",    value: `${sys?.cache_hit_rate_pct?.toFixed(1) ?? 0}%`, icon: PieChart, color: "text-violet-500", bg: "bg-violet-500/10" },
        ].map((kpi, i) => (
          <div key={i} className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 p-5 flex flex-col gap-2 shadow-sm">
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-500 dark:text-slate-400">{kpi.label}</span>
              <div className={`p-2 rounded-md ${kpi.bg} ${kpi.color}`}>
                <kpi.icon size={15} />
              </div>
            </div>
            <div className="text-2xl font-bold">{kpi.value}</div>
          </div>
        ))}
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        {/* Daily Token Usage chart */}
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 p-6 shadow-sm">
          <div className="flex items-center gap-2 mb-4">
            <Zap size={16} className="text-amber-500" />
            <h3 className="font-semibold text-sm">Daily Token Usage — Last 7 Days</h3>
          </div>
          <BarChart
            data={tokens?.days ?? []}
            valueKey="tokens"
            labelKey="date"
            color="#f59e0b"
          />
          <div className="mt-3 flex justify-between text-xs text-slate-400">
            <span>Estimated cost: ${tokens?.days?.reduce((s: number, d) => s + d.cost_usd, 0)?.toFixed(4) ?? "0"}</span>
            <span>{totalTokens.toLocaleString()} tokens total</span>
          </div>
        </div>

        {/* Daily Requests chart */}
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 p-6 shadow-sm">
          <div className="flex items-center gap-2 mb-4">
            <Activity size={16} className="text-indigo-500" />
            <h3 className="font-semibold text-sm">Daily Requests — Last 7 Days</h3>
          </div>
          <BarChart
            data={tokens?.days ?? []}
            valueKey="requests"
            labelKey="date"
            color="#6366f1"
          />
        </div>

        {/* Latency by model */}
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 p-6 shadow-sm">
          <div className="flex items-center gap-2 mb-5">
            <TrendingUp size={16} className="text-emerald-500" />
            <h3 className="font-semibold text-sm">Response Latency by Model (ms)</h3>
          </div>
          {Object.keys(latencyByModel).length === 0 ? (
            <div className="text-sm text-slate-400 text-center py-4">No latency data yet</div>
          ) : (
            <div className="space-y-4">
              {Object.entries(latencyByModel).map(([model, stats]) => (
                <div key={model}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium">{model}</span>
                    <span className="text-xs text-slate-400">{stats.count} requests</span>
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    {(["p50", "p95", "p99"] as const).map(p => (
                      <div key={p} className="rounded-lg bg-slate-50 dark:bg-slate-800 p-3 text-center">
                        <div className="text-xs text-slate-400 mb-1">{p.toUpperCase()}</div>
                        <div className="text-base font-bold text-emerald-500">{stats[p]}ms</div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Intent breakdown */}
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 p-6 shadow-sm">
          <div className="flex items-center gap-2 mb-5">
            <PieChart size={16} className="text-violet-500" />
            <h3 className="font-semibold text-sm">Intent Breakdown</h3>
          </div>
          {intentList.length === 0 ? (
            <div className="text-sm text-slate-400 text-center py-4">No intent data yet</div>
          ) : (
            <div>
              {intentList.map((it: IntentMetric) => (
                <HorizBar
                  key={it.intent}
                  label={it.intent}
                  pct={it.pct}
                  count={it.count}
                  color={INTENT_COLORS[it.intent] ?? "#64748b"}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
