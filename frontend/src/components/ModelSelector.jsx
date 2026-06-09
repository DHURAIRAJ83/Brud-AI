/**
 * Phase 4: Model Selector
 * Top-right dropdown for choosing TinyLlama / Mistral / Llama3 / Auto.
 * Persists selection to localStorage.
 */

import React, { useState, useEffect } from 'react';

const MODELS = [
  { value: 'auto',      label: '✨ Auto',      desc: 'Smart routing based on query complexity' },
  { value: 'tinyllama', label: '⚡ TinyLlama', desc: 'Fast · Simple queries'                   },
  { value: 'mistral',   label: '⚖️ Mistral',   desc: 'Balanced · Medium complexity'            },
  { value: 'llama3',    label: '🧠 Llama3',    desc: 'Powerful · Complex reasoning'            },
];

const MODEL_COLORS = {
  auto:      { color: '#c4b5fd', bg: 'rgba(167,139,250,0.12)', border: 'rgba(167,139,250,0.3)' },
  tinyllama: { color: '#34d399', bg: 'rgba(52,211,153,0.12)',  border: 'rgba(52,211,153,0.3)'  },
  mistral:   { color: '#f59e0b', bg: 'rgba(245,158,11,0.12)',  border: 'rgba(245,158,11,0.3)'  },
  llama3:    { color: '#60a5fa', bg: 'rgba(96,165,250,0.12)',  border: 'rgba(96,165,250,0.3)'  },
};

const LS_KEY = 'tamil_ai_model';

export function getSelectedModel() {
  return localStorage.getItem(LS_KEY) || 'auto';
}

export default function ModelSelector({ onChange }) {
  const [selected, setSelected] = useState(() => getSelectedModel());
  const [open, setOpen] = useState(false);

  useEffect(() => {
    onChange?.(selected);
  }, [selected, onChange]);

  const handleSelect = (value) => {
    localStorage.setItem(LS_KEY, value);
    setSelected(value);
    setOpen(false);
    onChange?.(value);
  };

  const cfg = MODEL_COLORS[selected] || MODEL_COLORS.auto;
  const activeLabel = MODELS.find(m => m.value === selected)?.label || '✨ Auto';

  return (
    <div style={{ position: 'relative' }}>
      <button
        id="model-selector-btn"
        onClick={() => setOpen(o => !o)}
        title="Select AI model"
        style={{
          display: 'flex', alignItems: 'center', gap: '0.4rem',
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
          whiteSpace: 'nowrap',
        }}
      >
        {activeLabel}
        <svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor" style={{ opacity: 0.7 }}>
          <path d="M1 3l4 4 4-4" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round"/>
        </svg>
      </button>

      {open && (
        <>
          <div
            onClick={() => setOpen(false)}
            style={{ position: 'fixed', inset: 0, zIndex: 999 }}
          />
          <div style={{
            position: 'absolute', top: 'calc(100% + 8px)', right: 0,
            width: 240, zIndex: 1000,
            background: '#12121e',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 12,
            boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
            overflow: 'hidden',
            animation: 'fadeSlideIn 0.15s ease',
          }}>
            <div style={{
              padding: '0.6rem 1rem',
              borderBottom: '1px solid rgba(255,255,255,0.06)',
              fontSize: '0.7rem', fontWeight: 700,
              color: 'rgba(255,255,255,0.5)',
              letterSpacing: '0.08em',
            }}>
              SELECT MODEL
            </div>
            {MODELS.map(m => {
              const mc = MODEL_COLORS[m.value];
              const isActive = selected === m.value;
              return (
                <button
                  key={m.value}
                  id={`model-opt-${m.value}`}
                  onClick={() => handleSelect(m.value)}
                  style={{
                    width: '100%', textAlign: 'left',
                    padding: '0.55rem 1rem',
                    background: isActive ? mc.bg : 'transparent',
                    border: 'none',
                    borderLeft: isActive ? `3px solid ${mc.color}` : '3px solid transparent',
                    cursor: 'pointer',
                    fontFamily: 'inherit',
                    transition: 'all 0.12s',
                    display: 'flex', flexDirection: 'column', gap: '2px',
                  }}
                >
                  <span style={{
                    fontSize: '0.8rem', fontWeight: 600,
                    color: isActive ? mc.color : 'rgba(255,255,255,0.75)',
                  }}>
                    {m.label}
                  </span>
                  <span style={{ fontSize: '0.68rem', color: 'rgba(255,255,255,0.35)' }}>
                    {m.desc}
                  </span>
                </button>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
