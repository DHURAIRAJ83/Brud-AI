/**
 * Phase 4: Runtime Status Widget
 * Shows current AI runtime (Local / Cloud / Hybrid) and active model.
 * Polls /api/runtime/status every 30 s and emits a cloud banner when needed.
 */

import React, { useEffect, useState, useCallback } from 'react';
import { getRuntimeStatus, setRuntimeMode, getModels } from '../services/api';

// Runtime badge configs
const RUNTIME_CONFIG = {
  local:  { emoji: '🟢', label: 'Local AI',  color: '#22d3a5', bg: 'rgba(34,211,165,0.12)',  border: 'rgba(34,211,165,0.3)'  },
  cloud:  { emoji: '🔵', label: 'Cloud AI',  color: '#60a5fa', bg: 'rgba(96,165,250,0.12)',   border: 'rgba(96,165,250,0.3)'   },
  hybrid: { emoji: '🟣', label: 'Hybrid AI', color: '#a78bfa', bg: 'rgba(167,139,250,0.12)', border: 'rgba(167,139,250,0.3)' },
  none:   { emoji: '⚫', label: 'No AI',     color: '#ef4444', bg: 'rgba(239,68,68,0.12)',   border: 'rgba(239,68,68,0.3)'   },
};

const MODE_OPTIONS = [
  { value: 'hybrid', label: '🟣 Hybrid (Recommended)' },
  { value: 'local',  label: '🟢 Local Only' },
  { value: 'cloud',  label: '🔵 Cloud Only' },
];

export default function RuntimeWidget({ onRuntimeChange }) {
  const [status, setStatus] = useState(null);
  const [showPanel, setShowPanel] = useState(false);
  const [switching, setSwitching] = useState(false);
  const [error, setError] = useState('');

  const fetchStatus = useCallback(async () => {
    try {
      const data = await getRuntimeStatus();
      setStatus(data);
      onRuntimeChange?.(data);
      setError('');
    } catch {
      setError('Backend unreachable');
    }
  }, [onRuntimeChange]);

  useEffect(() => {
    fetchStatus();
    const iv = setInterval(fetchStatus, 30000);
    return () => clearInterval(iv);
  }, [fetchStatus]);

  const handleModeSwitch = async (mode) => {
    setSwitching(true);
    try {
      await setRuntimeMode(mode);
      await fetchStatus();
    } catch (e) {
      setError(e.message);
    } finally {
      setSwitching(false);
    }
  };

  if (!status && !error) return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '0.4rem',
      padding: '0.3rem 0.75rem',
      borderRadius: '999px',
      background: 'rgba(255,255,255,0.05)',
      border: '1px solid rgba(255,255,255,0.1)',
      fontSize: '0.75rem',
      color: 'rgba(255,255,255,0.4)',
      animation: 'pulse 1.5s ease-in-out infinite',
    }}>
      ⏳ Checking AI…
    </div>
  );

  const cfg = RUNTIME_CONFIG[status?.runtime || 'none'];

  return (
    <div style={{ position: 'relative' }}>
      {/* Status pill */}
      <button
        id="runtime-widget-btn"
        onClick={() => setShowPanel(p => !p)}
        title="Click to manage AI runtime"
        style={{
          display: 'flex', alignItems: 'center', gap: '0.5rem',
          padding: '0.3rem 0.85rem',
          borderRadius: '999px',
          background: cfg.bg,
          border: `1px solid ${cfg.border}`,
          color: cfg.color,
          fontSize: '0.75rem',
          fontWeight: 600,
          cursor: 'pointer',
          fontFamily: 'inherit',
          transition: 'all 0.2s ease',
          backdropFilter: 'blur(8px)',
          userSelect: 'none',
        }}
      >
        <span style={{ fontSize: '0.85rem' }}>{cfg.emoji}</span>
        <span>{cfg.label}</span>
        {status?.active_model && (
          <span style={{
            padding: '1px 6px',
            borderRadius: '999px',
            background: 'rgba(255,255,255,0.08)',
            fontSize: '0.68rem',
            color: 'rgba(255,255,255,0.7)',
          }}>
            {status.active_model}
          </span>
        )}
        <svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor" style={{ opacity: 0.7 }}>
          <path d="M1 3l4 4 4-4" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round"/>
        </svg>
      </button>

      {/* Dropdown panel */}
      {showPanel && (
        <>
          {/* Backdrop */}
          <div
            onClick={() => setShowPanel(false)}
            style={{
              position: 'fixed', inset: 0, zIndex: 999,
            }}
          />
          <div style={{
            position: 'absolute', top: 'calc(100% + 8px)', right: 0,
            width: 300, zIndex: 1000,
            background: '#12121e',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 12,
            boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
            overflow: 'hidden',
            animation: 'fadeSlideIn 0.15s ease',
          }}>
            {/* Header */}
            <div style={{
              padding: '0.75rem 1rem',
              background: 'rgba(255,255,255,0.03)',
              borderBottom: '1px solid rgba(255,255,255,0.06)',
              fontWeight: 700, fontSize: '0.8rem', color: 'rgba(255,255,255,0.8)',
            }}>
              ⚙️ AI Runtime Control
            </div>

            {/* Status grid */}
            <div style={{ padding: '0.75rem 1rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <StatusRow label="Mode" value={status?.mode?.toUpperCase() || '—'} color="#a78bfa" />
              <StatusRow label="Active" value={cfg.label} color={cfg.color} />
              <StatusRow
                label="Local Ollama"
                value={status?.local_available ? '✅ Online' : '❌ Offline'}
                color={status?.local_available ? '#22d3a5' : '#ef4444'}
              />
              <StatusRow
                label="Cloud AI"
                value={status?.cloud_available ? '✅ Online' : '❌ Offline'}
                color={status?.cloud_available ? '#22d3a5' : '#ef4444'}
              />
              <StatusRow label="Failovers" value={status?.failover_count ?? 0} color="#f59e0b" />
            </div>

            {/* Mode switcher */}
            <div style={{
              padding: '0.5rem 1rem 0.75rem',
              borderTop: '1px solid rgba(255,255,255,0.06)',
            }}>
              <div style={{ fontSize: '0.7rem', color: 'rgba(255,255,255,0.4)', marginBottom: '0.4rem' }}>
                SWITCH MODE
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
                {MODE_OPTIONS.map(opt => (
                  <button
                    key={opt.value}
                    id={`runtime-mode-${opt.value}`}
                    disabled={switching || status?.mode === opt.value}
                    onClick={() => handleModeSwitch(opt.value)}
                    style={{
                      padding: '0.4rem 0.75rem',
                      borderRadius: 8,
                      border: status?.mode === opt.value
                        ? '1px solid rgba(124,92,252,0.5)'
                        : '1px solid rgba(255,255,255,0.06)',
                      background: status?.mode === opt.value
                        ? 'rgba(124,92,252,0.15)'
                        : 'transparent',
                      color: status?.mode === opt.value
                        ? '#c4b5fd'
                        : 'rgba(255,255,255,0.6)',
                      fontSize: '0.78rem',
                      cursor: status?.mode === opt.value ? 'default' : 'pointer',
                      fontFamily: 'inherit',
                      textAlign: 'left',
                      transition: 'all 0.15s',
                    }}
                  >
                    {switching ? '⏳ Switching…' : opt.label}
                  </button>
                ))}
              </div>
            </div>

            {error && (
              <div style={{
                padding: '0.5rem 1rem',
                background: 'rgba(239,68,68,0.1)',
                color: '#ef4444',
                fontSize: '0.75rem',
              }}>
                ⚠️ {error}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function StatusRow({ label, value, color }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.78rem' }}>
      <span style={{ color: 'rgba(255,255,255,0.45)' }}>{label}</span>
      <span style={{ color: color || 'rgba(255,255,255,0.85)', fontWeight: 600 }}>{value}</span>
    </div>
  );
}

// ── Cloud Banner ──────────────────────────────────────────────────────────────

export function CloudBanner({ visible }) {
  if (!visible) return null;
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem',
      padding: '0.4rem 1rem',
      background: 'linear-gradient(90deg, rgba(96,165,250,0.15), rgba(167,139,250,0.15))',
      borderBottom: '1px solid rgba(96,165,250,0.25)',
      fontSize: '0.78rem', color: '#93c5fd', fontWeight: 500,
      animation: 'fadeSlideIn 0.3s ease',
    }}>
      <span style={{ animation: 'pulse 2s ease-in-out infinite' }}>🔵</span>
      Running on <strong>Cloud AI</strong> — Local Ollama is offline. Messages are securely processed by our VPS.
    </div>
  );
}
