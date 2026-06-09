import React, { useState, useEffect, useRef } from 'react';
import {
  systemStatus, retrain, clearMemory, clearCache,
  uploadFile, listFiles, deleteFile,
  getMetrics, setModelOverride,
  getRuntimeStatus, setRuntimeMode, setRuntimeModel, getModels, refreshRuntime, adminRuntimeDashboard,
} from '../services/api';

function StatCard({ label, value, sub, icon, accent }) {
  return (
    <div className="card">
      <div className="card-title">{icon} {label}</div>
      <div className="stat-value" style={accent ? { color: accent } : {}}>{value ?? '—'}</div>
      {sub && <div className="stat-label">{sub}</div>}
    </div>
  );
}

function ProgressBar({ value = 0, max = 100, color }) {
  const pct = Math.min(100, Math.round((value / Math.max(max, 1)) * 100));
  return (
    <div className="progress-bar-wrap">
      <div className="progress-bar-fill" style={{ width: `${pct}%`, background: color }} />
    </div>
  );
}

function MetricsTab({ metrics }) {
  if (!metrics) return <div style={{ color: 'var(--color-text-muted)' }}>Loading metrics…</div>;
  const s = metrics.system || {};
  const lat = s.latency_ms || {};
  const recent = s.recent_5min || {};
  const intents = s.intent_distribution || {};
  const models = s.model_usage || {};

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div className="admin-grid">
        <StatCard label="Total Requests" icon="📊" value={s.total_requests ?? 0} sub={`${s.total_errors ?? 0} errors`} />
        <StatCard label="Error Rate" icon="🚨"
          value={s.error_rate != null ? `${(s.error_rate * 100).toFixed(1)}%` : '—'}
          accent={s.error_rate > 0.05 ? 'var(--color-error)' : 'var(--color-success)'}
          sub="< 5% is healthy" />
        <StatCard label="Avg Latency" icon="⚡" value={lat.avg ? `${lat.avg}ms` : '—'} sub={`p95: ${lat.p95 ?? '—'}ms`} />
        <StatCard label="Req/sec (5min)" icon="📈" value={recent.requests_per_second ?? 0} sub={`${recent.total_tokens_estimated ?? 0} tokens`} />
      </div>

      {/* Intent distribution */}
      {Object.keys(intents).length > 0 && (
        <div className="card">
          <div className="card-title">🎯 Intent Distribution</div>
          {Object.entries(intents).sort((a, b) => b[1] - a[1]).map(([intent, count]) => (
            <div key={intent} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.4rem' }}>
              <span style={{ minWidth: 100, fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>{intent}</span>
              <ProgressBar value={count} max={Math.max(...Object.values(intents))} color="linear-gradient(90deg, var(--color-accent), var(--color-teal))" />
              <span style={{ fontSize: '0.75rem', color: 'var(--color-text-faint)', minWidth: 30 }}>{count}</span>
            </div>
          ))}
        </div>
      )}

      {/* Model usage */}
      {Object.keys(models).length > 0 && (
        <div className="card">
          <div className="card-title">🤖 Model Usage</div>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            {Object.entries(models).map(([m, c]) => (
              <div key={m} style={{
                padding: '0.4rem 0.75rem',
                borderRadius: 'var(--radius-full)',
                background: 'rgba(245,158,11,0.15)',
                border: '1px solid rgba(245,158,11,0.3)',
                color: 'var(--color-warning)',
                fontSize: '0.8rem',
              }}>
                {m}: <strong>{c}</strong>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function PluginsTab({ metrics }) {
  const plugins = metrics?.plugins || [];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      {plugins.map((p, i) => (
        <div key={i} className="card" style={{ flexDirection: 'row', alignItems: 'center', gap: '1rem' }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{p.name}</div>
            <div style={{ color: 'var(--color-text-muted)', fontSize: '0.78rem' }}>{p.description}</div>
            <div style={{ display: 'flex', gap: '0.4rem', marginTop: '0.4rem', flexWrap: 'wrap' }}>
              {(p.intents || []).map(intent => (
                <span key={intent} className="intent-tag">{intent}</span>
              ))}
            </div>
          </div>
          <span style={{
            padding: '0.2rem 0.6rem',
            borderRadius: 'var(--radius-full)',
            background: p.source === 'builtin' ? 'rgba(34,211,165,0.1)' : 'rgba(124,92,252,0.1)',
            color: p.source === 'builtin' ? 'var(--color-success)' : 'var(--color-accent-light)',
            border: `1px solid ${p.source === 'builtin' ? 'rgba(34,211,165,0.3)' : 'rgba(124,92,252,0.3)'}`,
            fontSize: '0.7rem',
          }}>
            {p.source === 'builtin' ? 'built-in' : 'plugin'}
          </span>
        </div>
      ))}
    </div>
  );
}

// ── Runtime Dashboard Tab (Phase 4) ──────────────────────────────────────────
function RuntimeDashboardTab() {
  const [rt, setRt]             = useState(null);
  const [models, setModels]     = useState({ local: [], cloud: [] });
  const [loading, setLoading]   = useState(true);
  const [switching, setSwitching] = useState(false);
  const [msg, setMsg]           = useState('');

  const notify = (m) => { setMsg(m); setTimeout(() => setMsg(''), 4000); };

  const fetchRt = async () => {
    try {
      const [rtData, mdData] = await Promise.all([
        adminRuntimeDashboard(),
        getModels(),
      ]);
      setRt(rtData.runtime);
      setModels(mdData);
    } catch (e) {
      // fallback
      try {
        const rtData = await getRuntimeStatus();
        setRt(rtData);
      } catch {}
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchRt(); }, []);

  const handleModeSwitch = async (mode) => {
    setSwitching(true);
    try {
      await setRuntimeMode(mode);
      await fetchRt();
      notify(`✅ Switched to ${mode} mode`);
    } catch (e) { notify(`❌ ${e.message}`); }
    finally { setSwitching(false); }
  };

  const handleModelSet = async (model) => {
    try {
      await setRuntimeModel(model);
      await fetchRt();
      notify(`✅ Active model set to ${model}`);
    } catch (e) { notify(`❌ ${e.message}`); }
  };

  const handleRefresh = async () => {
    try {
      await refreshRuntime();
      await fetchRt();
      notify('✅ Runtime endpoints re-probed');
    } catch (e) { notify(`❌ ${e.message}`); }
  };

  const RUNTIME_COLORS = {
    local:  { color: '#22d3a5', bg: 'rgba(34,211,165,0.12)',  border: 'rgba(34,211,165,0.3)'  },
    cloud:  { color: '#60a5fa', bg: 'rgba(96,165,250,0.12)',  border: 'rgba(96,165,250,0.3)'  },
    hybrid: { color: '#a78bfa', bg: 'rgba(167,139,250,0.12)', border: 'rgba(167,139,250,0.3)' },
    none:   { color: '#ef4444', bg: 'rgba(239,68,68,0.12)',   border: 'rgba(239,68,68,0.3)'   },
  };

  if (loading) return <div style={{ color: 'var(--color-text-muted)', padding: '1rem' }}>Loading runtime data…</div>;

  const active = rt?.active || rt?.runtime || 'none';
  const mode   = rt?.mode   || 'hybrid';
  const rtCfg  = RUNTIME_COLORS[active] || RUNTIME_COLORS.none;
  const modeCfg = RUNTIME_COLORS[mode]  || RUNTIME_COLORS.hybrid;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {msg && (
        <div style={{
          padding: '0.75rem 1rem', borderRadius: 'var(--radius-md)',
          background: msg.includes('❌') ? 'rgba(239,68,68,0.1)' : 'rgba(34,211,165,0.1)',
          border: `1px solid ${msg.includes('❌') ? 'rgba(239,68,68,0.3)' : 'rgba(34,211,165,0.3)'}`,
          color: msg.includes('❌') ? 'var(--color-error)' : 'var(--color-success)',
          fontSize: '0.875rem',
        }}>{msg}</div>
      )}

      {/* Status Cards */}
      <div className="admin-grid">
        <StatCard label="Current Runtime" icon="⚡"
          value={active.toUpperCase()}
          accent={rtCfg.color}
          sub={`Mode: ${mode.toUpperCase()}`} />
        <StatCard label="Active Model" icon="🤖"
          value={rt?.active_model || '—'}
          sub="Auto-routed by query complexity" />
        <StatCard label="Local Ollama" icon="🖥️"
          value={rt?.local_available ? 'Online ✅' : 'Offline ❌'}
          accent={rt?.local_available ? 'var(--color-success)' : 'var(--color-error)'}
          sub="localhost:11434" />
        <StatCard label="Failovers" icon="🔄"
          value={rt?.failover_count ?? 0}
          accent="var(--color-warning)"
          sub="Local → Cloud switches" />
      </div>

      {/* Mode Switcher */}
      <div className="card">
        <div className="card-title">🔀 Switch Runtime Mode</div>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          {['local', 'cloud', 'hybrid'].map(m => {
            const cfg = RUNTIME_COLORS[m];
            const isActive = mode === m;
            return (
              <button key={m}
                id={`admin-mode-${m}`}
                disabled={switching || isActive}
                onClick={() => handleModeSwitch(m)}
                style={{
                  padding: '0.5rem 1.25rem',
                  borderRadius: 'var(--radius-full)',
                  border: `1px solid ${isActive ? cfg.border : 'var(--color-border)'}`,
                  background: isActive ? cfg.bg : 'transparent',
                  color: isActive ? cfg.color : 'var(--color-text-muted)',
                  fontWeight: isActive ? 700 : 500,
                  cursor: isActive ? 'default' : 'pointer',
                  fontSize: '0.82rem', fontFamily: 'inherit',
                  transition: 'all 0.15s',
                  textTransform: 'capitalize',
                }}
              >
                {m === 'local' ? '🟢' : m === 'cloud' ? '🔵' : '🟣'} {m}
                {isActive && ' (active)'}
              </button>
            );
          })}
          <button className="btn btn-ghost" onClick={handleRefresh}
            style={{ marginLeft: 'auto', fontSize: '0.8rem' }}>
            ↻ Re-probe
          </button>
        </div>
        <div style={{ fontSize: '0.75rem', color: 'var(--color-text-faint)', marginTop: '0.5rem' }}>
          <strong>Hybrid</strong> (recommended): tries local first, auto-falls back to cloud.
        </div>
      </div>

      {/* Model Override */}
      <div className="card">
        <div className="card-title">🤖 Active Model Override</div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          {['tinyllama', 'mistral', 'llama3'].map(m => {
            const isActive = (rt?.active_model || '') === m;
            return (
              <button key={m}
                id={`admin-model-${m}`}
                onClick={() => handleModelSet(m)}
                style={{
                  padding: '0.4rem 1rem',
                  borderRadius: 'var(--radius-full)',
                  border: `1px solid ${isActive ? 'rgba(245,158,11,0.5)' : 'var(--color-border)'}`,
                  background: isActive ? 'rgba(245,158,11,0.15)' : 'transparent',
                  color: isActive ? 'var(--color-warning)' : 'var(--color-text-muted)',
                  cursor: 'pointer', fontSize: '0.8rem', fontFamily: 'inherit',
                  fontWeight: isActive ? 700 : 500, transition: 'all 0.15s',
                }}
              >
                {m === 'tinyllama' ? '⚡' : m === 'mistral' ? '⚖️' : '🧠'} {m}
              </button>
            );
          })}
        </div>
      </div>

      {/* Available Models */}
      <div className="card">
        <div className="card-title">📦 Available Models</div>
        <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontSize: '0.72rem', color: 'var(--color-text-faint)', marginBottom: '0.4rem', fontWeight: 700 }}>🖥️ LOCAL</div>
            {(models.local || []).length === 0
              ? <span style={{ color: 'var(--color-text-faint)', fontSize: '0.8rem' }}>None detected</span>
              : (models.local || []).map(m => (
                <div key={m} style={{
                  padding: '0.25rem 0.6rem', borderRadius: 'var(--radius-full)',
                  background: 'rgba(34,211,165,0.1)', border: '1px solid rgba(34,211,165,0.25)',
                  color: '#22d3a5', fontSize: '0.78rem', marginBottom: '0.3rem', display: 'inline-block', marginRight: '0.4rem',
                }}>{m}</div>
              ))
            }
          </div>
          <div>
            <div style={{ fontSize: '0.72rem', color: 'var(--color-text-faint)', marginBottom: '0.4rem', fontWeight: 700 }}>☁️ CLOUD</div>
            {(models.cloud || []).length === 0
              ? <span style={{ color: 'var(--color-text-faint)', fontSize: '0.8rem' }}>None configured</span>
              : (models.cloud || []).map(m => (
                <div key={m} style={{
                  padding: '0.25rem 0.6rem', borderRadius: 'var(--radius-full)',
                  background: 'rgba(96,165,250,0.1)', border: '1px solid rgba(96,165,250,0.25)',
                  color: '#60a5fa', fontSize: '0.78rem', marginBottom: '0.3rem', display: 'inline-block', marginRight: '0.4rem',
                }}>{m}</div>
              ))
            }
          </div>
        </div>
      </div>

      {/* Auto-routing legend */}
      <div className="card">
        <div className="card-title">🧠 Auto Model Routing</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.83rem' }}>
          {[
            { model: 'TinyLlama ⚡', score: 'Score 0–1', desc: 'Simple / short queries',     color: '#22d3a5' },
            { model: 'Mistral ⚖️',   score: 'Score 2–3', desc: 'Medium complexity queries',  color: '#f59e0b' },
            { model: 'Llama3 🧠',    score: 'Score 4+',  desc: 'Complex / technical queries', color: '#60a5fa' },
          ].map(row => (
            <div key={row.model} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <span style={{ color: row.color, fontWeight: 700, minWidth: 110 }}>{row.model}</span>
              <span style={{
                padding: '1px 8px', borderRadius: 'var(--radius-full)',
                background: 'rgba(255,255,255,0.05)', fontSize: '0.7rem',
                color: 'var(--color-text-faint)', minWidth: 60, textAlign: 'center',
              }}>{row.score}</span>
              <span style={{ color: 'var(--color-text-muted)' }}>{row.desc}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}


export default function AdminView() {
  const [status, setStatus] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [actionMsg, setActionMsg] = useState('');
  const [activeTab, setActiveTab] = useState('overview');
  const [modelOverride, setModelOverride] = useState('');
  const fileInputRef = useRef(null);

  const fetchAll = async () => {
    try {
      const [s, m] = await Promise.all([systemStatus(), getMetrics()]);
      setStatus(s);
      setMetrics(m);
    } catch (e) {
      setActionMsg(`⚠️ Backend error: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAll(); }, []);

  const notify = (msg) => { setActionMsg(msg); setTimeout(() => setActionMsg(''), 4000); };

  const handleUpload = async (file) => {
    if (!file) return;
    setUploading(true);
    try {
      const res = await uploadFile(file);
      notify(`✅ "${file.name}" → ${res.chunks_indexed} chunks indexed`);
      fetchAll();
    } catch (e) { notify(`❌ ${e.message}`); }
    finally { setUploading(false); }
  };

  const handleModelOverride = async () => {
    try {
      const res = await setModelOverride(modelOverride || null);
      notify(`✅ ${res.message}`);
      fetchAll();
    } catch (e) { notify(`❌ ${e.message}`); }
  };

  const handleAction = async (fn, label) => {
    try {
      const res = await fn();
      notify(`✅ ${label}: ${res.message}`);
      fetchAll();
    } catch (e) { notify(`❌ ${label}: ${e.message}`); }
  };

  const files = status?.files || [];
  const tabs = ['overview', 'runtime', 'metrics', 'plugins', 'routing', 'files'];

  return (
    <div className="admin-view">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h2 style={{ fontSize: '1.4rem', fontWeight: 700 }}>Admin Panel v2</h2>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>System control, monitoring, plugins, model routing</p>
        </div>
        <button className="btn btn-ghost" onClick={fetchAll}>↻ Refresh</button>
      </div>

      {actionMsg && (
        <div style={{
          padding: '0.75rem 1rem', borderRadius: 'var(--radius-md)',
          background: actionMsg.includes('❌') ? 'rgba(239,68,68,0.1)' : 'rgba(34,211,165,0.1)',
          border: `1px solid ${actionMsg.includes('❌') ? 'rgba(239,68,68,0.3)' : 'rgba(34,211,165,0.3)'}`,
          color: actionMsg.includes('❌') ? 'var(--color-error)' : 'var(--color-success)',
          fontSize: '0.875rem',
        }}>
          {actionMsg}
        </div>
      )}

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '0.25rem', borderBottom: '1px solid var(--color-border)', paddingBottom: '0.5rem' }}>
        {tabs.map(tab => (
          <button key={tab} id={`tab-${tab}`}
            onClick={() => setActiveTab(tab)}
            style={{
              padding: '0.4rem 1rem', borderRadius: 'var(--radius-md)',
              border: 'none', cursor: 'pointer', fontFamily: 'inherit',
              fontSize: '0.8rem', fontWeight: 500, textTransform: 'capitalize',
              background: activeTab === tab ? 'rgba(124,92,252,0.2)' : 'transparent',
              color: activeTab === tab ? 'var(--color-accent-light)' : 'var(--color-text-muted)',
              borderBottom: activeTab === tab ? '2px solid var(--color-accent)' : '2px solid transparent',
              transition: 'all 0.15s',
            }}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'overview' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div className="admin-grid">
            <StatCard label="Ollama" icon="🤖"
              value={loading ? '…' : (status?.ollama?.alive ? 'Online' : 'Offline')}
              sub={status?.ollama?.models?.join(', ') || '—'}
              accent={status?.ollama?.alive ? 'var(--color-success)' : 'var(--color-error)'}
            />
            <StatCard label="RAG Chunks" icon="📚" value={loading ? '…' : (status?.rag?.total_chunks ?? 0)} sub={`${status?.rag?.unique_sources ?? 0} source(s)`} />
            <StatCard label="Sessions" icon="💬" value={loading ? '…' : (status?.memory?.active_sessions ?? 0)} sub="Active memories" />
            <StatCard label="Cache Hit" icon="⚡" value={loading ? '…' : `${((status?.cache?.hit_rate ?? 0) * 100).toFixed(0)}%`} sub={`${status?.cache?.hits ?? 0} hits`} />
          </div>
          <div className="card">
            <div className="card-title">⚙️ Quick Actions</div>
            <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
              <button className="btn btn-primary" id="retrain-btn" onClick={() => handleAction(retrain, 'Retrain')}>🔁 Re-train RAG</button>
              <button className="btn btn-ghost" id="clear-memory-btn" onClick={() => handleAction(clearMemory, 'Clear Memory')}>🧹 Clear Memory</button>
              <button className="btn btn-ghost" id="clear-cache-btn" onClick={() => handleAction(clearCache, 'Clear Cache')}>⚡ Clear Cache</button>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'metrics'  && <MetricsTab metrics={metrics} />}
      {activeTab === 'plugins'  && <PluginsTab metrics={metrics} />}
      {activeTab === 'runtime'  && <RuntimeDashboardTab />}

      {activeTab === 'routing' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div className="card">
            <div className="card-title">🤖 Smart Model Routing</div>
            <div style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)', lineHeight: 1.6 }}>
              <strong>Auto routing:</strong><br />
              • Short/simple queries → <span style={{ color: 'var(--color-teal)' }}>TinyLlama</span> (fast)<br />
              • Complex/long queries → <span style={{ color: 'var(--color-accent-light)' }}>Mistral</span> (quality)<br />
              • Score based on: word count + intent + question count
            </div>
          </div>
          <div className="card">
            <div className="card-title">🔧 Model Override</div>
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
              <select
                value={modelOverride}
                onChange={e => setModelOverride(e.target.value)}
                style={{
                  background: 'var(--color-surface-3)', border: '1px solid var(--color-border)',
                  color: 'var(--color-text)', borderRadius: 'var(--radius-md)',
                  padding: '0.5rem 0.75rem', fontFamily: 'inherit', fontSize: '0.875rem',
                  flex: 1,
                }}
                id="model-select"
              >
                <option value="">Auto (Dynamic Routing)</option>
                <option value="tinyllama">tinyllama (Fast)</option>
                <option value="mistral">mistral (Balanced)</option>
                <option value="llama3">llama3 (Strong)</option>
              </select>
              <button className="btn btn-primary" onClick={handleModelOverride}>Apply</button>
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--color-text-faint)' }}>
              Override forces all requests to use one model, regardless of complexity.
            </div>
          </div>
        </div>
      )}

      {activeTab === 'files' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div className="card">
            <div className="card-title">📤 Upload Document</div>
            <div
              className={`drop-zone ${dragOver ? 'drag-over' : ''}`}
              onClick={() => fileInputRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => { e.preventDefault(); setDragOver(false); handleUpload(e.dataTransfer.files[0]); }}
              id="drop-zone"
            >
              <div className="drop-zone-icon">📁</div>
              <div style={{ fontWeight: 600 }}>{uploading ? 'Uploading…' : 'Drop or click to upload'}</div>
              <div style={{ fontSize: '0.75rem' }}>PDF · DOCX · TXT (max 20 MB)</div>
            </div>
            <input ref={fileInputRef} type="file" id="file-input"
              accept=".pdf,.docx,.doc,.txt" style={{ display: 'none' }}
              onChange={e => handleUpload(e.target.files[0])}
            />
          </div>
          {files.length > 0 && (
            <div className="card">
              <div className="card-title">🗂️ Indexed Documents ({files.length})</div>
              <div className="file-list">
                {files.map((f, i) => (
                  <div key={i} className="file-item">
                    <span>{f.name.endsWith('.pdf') ? '📄' : f.name.endsWith('.txt') ? '📝' : '📃'}</span>
                    <span className="file-name" title={f.name}>{f.name}</span>
                    <span className="file-size">{f.size_kb} KB</span>
                    <button className="btn btn-danger"
                      style={{ padding: '0.25rem 0.75rem', fontSize: '0.75rem' }}
                      onClick={() => handleAction(() => deleteFile(f.name), 'Delete')}
                    >Delete</button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
