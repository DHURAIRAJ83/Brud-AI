import { useState, useEffect } from "react";
import { apiService } from "../services/api";
import { 
  Mic, 
  Volume2, 
  CheckCircle2, 
  AlertCircle, 
  Play, 
  Pause,
  AlertTriangle, 
  VolumeX, 
  ShieldAlert,
  Zap, 
  ListFilter
} from "lucide-react";
import { format } from "date-fns";
import type { VoiceSession, VoiceAttempt, VoiceMetrics, VoiceSecurityMetrics } from "../types";

export function VoiceDashboard() {
  const [metrics, setMetrics] = useState<VoiceMetrics | null>(null);
  const [sessions, setSessions] = useState<VoiceSession[]>([]);
  const [securityMetrics, setSecurityMetrics] = useState<VoiceSecurityMetrics | null>(null);
  const [attempts, setAttempts] = useState<VoiceAttempt[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [playingId, setPlayingId] = useState<string | null>(null);
  const [activeAudio, setActiveAudio] = useState<HTMLAudioElement | null>(null);
  const [wsConnected, setWsConnected] = useState(false);

  // Common data fetch function
  const fetchData = async () => {
    try {
      const [metricsData, sessionsData, securityData, attemptsData] = await Promise.all([
        apiService.getVoiceMetrics(),
        apiService.getVoiceSessions(),
        apiService.getVoiceSecurityMetrics(),
        apiService.getVoiceAttempts()
      ]);
      setMetrics(metricsData);
      setSessions(sessionsData.sessions || []);
      setSecurityMetrics(securityData);
      setAttempts(attemptsData.attempts || []);
      setError(null);
    } catch (err) {
      console.error("Error loading voice metrics", err);
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  };

  // Poll voice sessions and metrics every 5 seconds
  useEffect(() => {
    const timer = setTimeout(() => {
      fetchData().catch(err => console.error("Initial fetch failed", err));
    }, 0);
    const interval = setInterval(() => {
      fetchData().catch(err => console.error("Interval fetch failed", err));
    }, 5000);
    return () => {
      clearTimeout(timer);
      clearInterval(interval);
    };
  }, []);

  // WebSocket connection for real-time updates
  useEffect(() => {
    let socket: WebSocket | null = null;
    let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;

    function connectWs() {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const host = window.location.hostname;
      const port = window.location.port === "3002" || window.location.port === "5173" || window.location.port === "3000" ? "8000" : window.location.port;
      const wsUrl = `${protocol}//${host}${port ? `:${port}` : ""}/api/ws/system-events`;
      
      console.log("Connecting to system events WebSocket:", wsUrl);
      socket = new WebSocket(wsUrl);

      socket.onopen = () => {
        console.log("Connected to system events WebSocket");
        setWsConnected(true);
      };

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log("WebSocket event received:", data);
          if (
            data.event === "voice_profile_updated" || 
            data.event === "user_changed" || 
            data.event === "skill_changed"
          ) {
            fetchData();
          }
        } catch (err) {
          console.error("Error parsing WebSocket event data:", err);
        }
      };

      socket.onclose = () => {
        console.log("Disconnected from system events WebSocket. Reconnecting in 3s...");
        setWsConnected(false);
        reconnectTimeout = setTimeout(connectWs, 3000);
      };

      socket.onerror = (err) => {
        console.error("WebSocket error:", err);
        socket?.close();
      };
    }

    connectWs();

    return () => {
      if (socket) {
        socket.onclose = null;
        socket.close();
      }
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
      }
    };
  }, []);

  const handlePlayAudio = (sessionId: string) => {
    if (playingId === sessionId) {
      if (activeAudio) {
        activeAudio.pause();
        setPlayingId(null);
        setActiveAudio(null);
      }
      return;
    }

    if (activeAudio) {
      activeAudio.pause();
    }

    const audioUrl = `/api/voice/audio/${sessionId}`;
    const audio = new Audio(audioUrl);
    
    audio.onended = () => {
      setPlayingId(null);
      setActiveAudio(null);
    };

    setActiveAudio(audio);
    setPlayingId(sessionId);
    
    audio.play().catch(err => {
      console.error("Audio playback failed", err);
      setPlayingId(null);
      setActiveAudio(null);
    });
  };

  if (loading && !metrics) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-8 w-48 bg-slate-200 dark:bg-slate-800 rounded"></div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map(n => (
            <div key={n} className="h-32 bg-slate-200 dark:bg-slate-800 rounded-xl"></div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 text-red-500 bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-800 rounded-xl">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <AlertCircle size={20} />
          Error Loading Voice Dashboard
        </h3>
        <p className="text-sm mt-1">{error.message || "Could not connect to voice analytics backend endpoints."}</p>
      </div>
    );
  }

  const statCards = [
    { title: "Total Voice Sessions", value: metrics?.total_sessions || 0, icon: Mic, color: "text-blue-500", bg: "bg-blue-500/10" },
    { title: "Average Confidence", value: `${Math.round((metrics?.average_confidence || 0) * 100)}%`, icon: CheckCircle2, color: "text-emerald-500", bg: "bg-emerald-500/10" },
    { title: "Failed Sessions", value: metrics?.failed_sessions || 0, icon: AlertCircle, color: "text-red-500", bg: "bg-red-500/10" },
    { title: "Wake Word Hits", value: metrics?.wakeword_hits || 0, icon: Zap, color: "text-violet-500", bg: "bg-violet-500/10" },
    { title: "Confirmation Requests", value: metrics?.confirmation_requests || 0, icon: ShieldAlert, color: "text-amber-500", bg: "bg-amber-500/10" },
    { title: "Rejected Commands", value: metrics?.rejected_commands || 0, icon: AlertTriangle, color: "text-amber-600", bg: "bg-amber-600/10" },
    { title: "Interrupted Speech", value: metrics?.interrupted_commands || 0, icon: VolumeX, color: "text-slate-500", bg: "bg-slate-500/10" },
  ];

  const securityCards = [
    { title: "Registered Profiles", value: securityMetrics?.enrolled_profiles_count || 0, icon: Mic, color: "text-emerald-500", bg: "bg-emerald-500/10" },
    { title: "Verification Success Rate", value: `${Math.round((securityMetrics?.success_rate || 0) * 100)}%`, icon: CheckCircle2, color: "text-blue-500", bg: "bg-blue-500/10" },
    { title: "Biometric Failures", value: securityMetrics?.failed_attempts || 0, icon: AlertCircle, color: "text-red-500", bg: "bg-red-500/10" },
    { title: "Account Lockouts", value: securityMetrics?.lockout_count || 0, icon: ShieldAlert, color: "text-orange-500", bg: "bg-orange-500/10" },
    { title: "Replay Blocks", value: securityMetrics?.replay_attack_count || 0, icon: AlertTriangle, color: "text-red-600", bg: "bg-red-600/10" },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight bg-gradient-to-r from-blue-500 to-indigo-500 bg-clip-text text-transparent">
            Skill-Aware Voice OS Console
          </h2>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Monitor hardware indicators, STT metrics, and active skill overrides.
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5 bg-slate-100 dark:bg-slate-800 px-2.5 py-1 rounded-full text-xs font-medium">
            <span className={`h-2 w-2 rounded-full ${wsConnected ? "bg-emerald-500" : "bg-red-500 animate-pulse"}`}></span>
            {wsConnected ? "Real-time Link Connected" : "Polling Mode"}
          </div>
          <div className="text-xs text-slate-400">
            Last updated: {format(new Date(), "HH:mm:ss")}
          </div>
        </div>
      </div>

      {/* Lockout Alert Banner */}
      {(securityMetrics?.lockout_count ?? 0) > 0 && (
        <div className="p-4 rounded-xl border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/20 text-red-700 dark:text-red-400 flex items-center gap-3 animate-pulse">
          <ShieldAlert size={24} className="flex-shrink-0" />
          <div>
            <h4 className="font-semibold text-sm">Security Alert: Voice Lockouts Recorded ({securityMetrics?.lockout_count})</h4>
            <p className="text-xs mt-0.5 opacity-90">
              Voice verification failures have triggered locks in this environment. Restrictive safety controls are active.
            </p>
          </div>
        </div>
      )}

      {/* Analytics Grid */}
      <div className="space-y-2">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Voice OS Metrics</h3>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
          {statCards.map((stat, i) => (
            <div key={i} className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 p-5 shadow-sm flex flex-col gap-2 hover:shadow-md transition-shadow">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">{stat.title}</span>
                <div className={`p-2 rounded-md ${stat.bg} ${stat.color}`}>
                  <stat.icon size={16} />
                </div>
              </div>
              <div className="text-xl font-bold">{stat.value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Security Biometrics Grid */}
      <div className="space-y-2">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Biometric Security Status</h3>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
          {securityCards.map((stat, i) => (
            <div key={i} className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 p-5 shadow-sm flex flex-col gap-2 hover:shadow-md transition-shadow">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">{stat.title}</span>
                <div className={`p-2 rounded-md ${stat.bg} ${stat.color}`}>
                  <stat.icon size={16} />
                </div>
              </div>
              <div className="text-xl font-bold">{stat.value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Hardware Status Cards */}
      <div className="grid gap-6 md:grid-cols-3">
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/40 p-6 flex items-center gap-4">
          <div className="p-3 bg-emerald-500/10 text-emerald-500 rounded-lg">
            <Mic size={24} />
          </div>
          <div>
            <h4 className="font-semibold">Microphone Status</h4>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">Realtek Mic (Index: default)</p>
            <span className="inline-flex items-center gap-1.5 text-xs text-emerald-500 font-medium mt-1">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-ping"></span>
              Capturing Online
            </span>
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/40 p-6 flex items-center gap-4">
          <div className="p-3 bg-blue-500/10 text-blue-500 rounded-lg">
            <Volume2 size={24} />
          </div>
          <div>
            <h4 className="font-semibold">Speaker Status</h4>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">Realtek Speakers (Index: default)</p>
            <span className="inline-flex items-center gap-1.5 text-xs text-emerald-500 font-medium mt-1">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500"></span>
              Ready
            </span>
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/40 p-6 flex items-center gap-4">
          <div className="p-3 bg-indigo-500/10 text-indigo-500 rounded-lg">
            <Zap size={24} />
          </div>
          <div>
            <h4 className="font-semibold">Wake Word Engine</h4>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">"Hey Rudran" / "ருத்ரன்"</p>
            <span className="inline-flex items-center gap-1.5 text-xs text-indigo-500 font-medium mt-1 bg-indigo-500/10 px-2 py-0.5 rounded-full">
              OpenWakeWord Active
            </span>
          </div>
        </div>
      </div>

      {/* Voice Sessions Log list */}
      <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">Voice Session Logs & Audio Replay</h3>
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <ListFilter size={14} />
            <span>Showing latest {sessions.length} audits</span>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm border-collapse">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-800 text-slate-400 font-medium">
                <th className="py-3 px-4">Session Date</th>
                <th className="py-3 px-4">Trigger</th>
                <th className="py-3 px-4">Transcript</th>
                <th className="py-3 px-4">STT Confidence</th>
                <th className="py-3 px-4">Active Skill</th>
                <th className="py-3 px-4">Duration</th>
                <th className="py-3 px-4">Flags</th>
                <th className="py-3 px-4 text-right">Debug</th>
              </tr>
            </thead>
            <tbody>
              {sessions.length === 0 ? (
                <tr>
                  <td colSpan={8} className="text-center py-8 text-slate-400">
                    No voice session records found. Speak "Hey Rudran" to trigger the voice pipeline.
                  </td>
                </tr>
              ) : (
                sessions.map((session: VoiceSession) => (
                  <tr key={session.id} className="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-900/40">
                    <td className="py-3.5 px-4 text-xs font-mono">
                      {format(new Date(session.created_at), "yyyy-MM-dd HH:mm:ss")}
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="text-xs bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded">
                        {session.wakeword || "PTT"}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 font-medium max-w-xs truncate" title={session.transcript}>
                      {session.transcript || <span className="text-slate-400 italic">No speech captured</span>}
                    </td>
                    <td className="py-3.5 px-4">
                      {session.confidence !== null ? (
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-mono w-8">{Math.round(session.confidence * 100)}%</span>
                          <div className="h-1.5 w-16 bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden">
                            <div 
                              className={`h-full rounded-full ${
                                session.confidence >= 0.75 
                                  ? "bg-emerald-500" 
                                  : session.confidence >= 0.60 
                                    ? "bg-amber-500" 
                                    : "bg-red-500"
                              }`} 
                              style={{ width: `${session.confidence * 100}%` }}
                            ></div>
                          </div>
                        </div>
                      ) : (
                        <span className="text-slate-400">-</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="text-xs text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20 px-2 py-0.5 rounded-full font-medium">
                        {session.skill_id || "assistant"}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-xs">
                      {session.duration_ms ? `${(session.duration_ms / 1000).toFixed(2)}s` : "-"}
                    </td>
                    <td className="py-3.5 px-4">
                      <div className="flex gap-1.5 flex-wrap">
                        {session.confirmation_required === 1 && (
                          <span className="text-[10px] bg-amber-100 dark:bg-amber-950/30 text-amber-700 dark:text-amber-400 px-1.5 py-0.5 rounded font-medium">
                            Confirmed
                          </span>
                        )}
                        {session.interrupted === 1 && (
                          <span className="text-[10px] bg-red-100 dark:bg-red-950/30 text-red-700 dark:text-red-400 px-1.5 py-0.5 rounded font-medium">
                            Interrupted
                          </span>
                        )}
                        {session.status === "cancelled" && (
                          <span className="text-[10px] bg-slate-100 dark:bg-slate-800 text-slate-500 px-1.5 py-0.5 rounded font-medium">
                            Rejected
                          </span>
                        )}
                        {session.status === "awaiting_approval" && (
                          <span className="text-[10px] bg-orange-100 dark:bg-orange-950/30 text-orange-700 dark:text-orange-400 px-1.5 py-0.5 rounded font-medium animate-pulse">
                            Needs Approval
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      {session.audio_file ? (
                        <button
                          onClick={() => handlePlayAudio(session.id)}
                          className={`p-1.5 rounded-full transition-colors ${
                            playingId === session.id 
                              ? "bg-emerald-500 text-white hover:bg-emerald-600" 
                              : "bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300"
                          }`}
                          title={playingId === session.id ? "Pause Replay" : "Replay Audio Command"}
                        >
                          {playingId === session.id ? <Pause size={14} /> : <Play size={14} />}
                        </button>
                      ) : (
                        <span className="text-xs text-slate-400 italic">No Audio</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Security Verification Attempts list */}
      <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">Biometric & Challenge Verification Timeline</h3>
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <ListFilter size={14} />
            <span>Showing latest {attempts.length} verification events</span>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm border-collapse">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-800 text-slate-400 font-medium">
                <th className="py-3 px-4">Timestamp</th>
                <th className="py-3 px-4">User</th>
                <th className="py-3 px-4">Confidence</th>
                <th className="py-3 px-4">Liveness Check</th>
                <th className="py-3 px-4">Status</th>
              </tr>
            </thead>
            <tbody>
              {attempts.length === 0 ? (
                <tr>
                  <td colSpan={5} className="text-center py-8 text-slate-400">
                    No verification attempts recorded.
                  </td>
                </tr>
              ) : (
                attempts.map((attempt: VoiceAttempt) => (
                  <tr key={attempt.id} className="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-900/40">
                    <td className="py-3.5 px-4 text-xs font-mono">
                      {format(new Date(attempt.created_at), "yyyy-MM-dd HH:mm:ss")}
                    </td>
                    <td className="py-3.5 px-4 text-xs">
                      {attempt.username || attempt.user_id}
                    </td>
                    <td className="py-3.5 px-4 font-mono">
                      {attempt.confidence_score !== null ? `${Math.round(attempt.confidence_score * 100)}%` : "-"}
                    </td>
                    <td className="py-3.5 px-4">
                      <span className={`text-xs px-2 py-0.5 rounded ${attempt.challenge_required ? "bg-amber-100 dark:bg-amber-950/30 text-amber-700 dark:text-amber-400" : "bg-slate-100 dark:bg-slate-800 text-slate-500"}`}>
                        {attempt.challenge_required ? "Challenge Required" : "Biometrics Only"}
                      </span>
                    </td>
                    <td className="py-3.5 px-4">
                      <span className={`text-xs px-2.5 py-1 rounded-full font-semibold ${
                        attempt.verification_status === "authorized" 
                          ? "bg-emerald-100 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-400" 
                          : attempt.verification_status === "confirm" 
                            ? "bg-amber-100 dark:bg-amber-950/30 text-amber-700 dark:text-amber-400" 
                            : attempt.verification_status === "locked_out" 
                              ? "bg-red-200 dark:bg-red-950 text-red-700 dark:text-red-300 font-bold" 
                              : "bg-red-100 dark:bg-red-950/30 text-red-700 dark:text-red-400"
                      }`}>
                        {attempt.verification_status.toUpperCase()}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
