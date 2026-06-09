import React, { useState, useEffect, useRef, createContext, useContext, useCallback } from 'react';
import ChatView from './components/ChatView';
import AdminView from './components/AdminView';
import MemoryPanel from './components/MemoryPanel';
import RuntimeWidget from './components/RuntimeWidget';
import ModelSelector, { getSelectedModel } from './components/ModelSelector';
import OnboardingModal from './components/OnboardingModal';
import { systemStatus, getRuntimeStatus } from './services/api';

// ── Runtime Context ───────────────────────────────────────────────────────────
export const RuntimeContext = createContext({
  runtime: null,
  selectedModel: 'auto',
  setSelectedModel: () => {},
});

export function useRuntime() {
  return useContext(RuntimeContext);
}

// Simple session ID stored in sessionStorage
function getSessionId() {
  let id = sessionStorage.getItem('tamil_ai_session');
  if (!id) {
    id = Math.random().toString(36).substring(2) + Date.now().toString(36);
    sessionStorage.setItem('tamil_ai_session', id);
  }
  return id;
}

const NAV_ITEMS = [
  { id: 'chat',   label: 'Chat',        icon: '💬' },
  { id: 'memory', label: 'Memory',      icon: '🧠' },
  { id: 'admin',  label: 'Admin Panel', icon: '⚙️' },
];

export default function App() {
  const [activeView, setActiveView]     = useState('chat');
  const [ollamaAlive, setOllamaAlive]   = useState(null);
  const [runtimeData, setRuntimeData]   = useState(null);
  const [selectedModel, setSelectedModel] = useState(() => getSelectedModel());
  const [showOnboarding, setShowOnboarding] = useState(false);
  const sessionId = useRef(getSessionId()).current;

  // ── Initial runtime check — show onboarding if local unavailable & no consent
  useEffect(() => {
    const checkRuntime = async () => {
      try {
        const rt = await getRuntimeStatus();
        setRuntimeData(rt);
        setOllamaAlive(rt.local_available);

        const hasConsent = localStorage.getItem('cloud_consent') === 'true';
        const aiMode     = localStorage.getItem('ai_mode');

        if (!rt.local_available && !hasConsent && aiMode !== 'cloud') {
          setShowOnboarding(true);
        }
      } catch {
        // Fallback to legacy status check
        try {
          const data = await systemStatus();
          setOllamaAlive(data?.ollama?.alive ?? false);
          if (!data?.ollama?.alive) {
            const hasConsent = localStorage.getItem('cloud_consent') === 'true';
            if (!hasConsent) setShowOnboarding(true);
          }
        } catch {
          setOllamaAlive(false);
        }
      }
    };
    checkRuntime();
    const iv = setInterval(checkRuntime, 30000);
    return () => clearInterval(iv);
  }, []);

  const handleRuntimeChange = useCallback((rt) => {
    setRuntimeData(rt);
    setOllamaAlive(rt.local_available);
  }, []);

  const handleCloudConsent = () => {
    setShowOnboarding(false);
  };

  const runtimeCtx = {
    runtime:        runtimeData,
    selectedModel,
    setSelectedModel,
  };

  return (
    <RuntimeContext.Provider value={runtimeCtx}>
      <div className="app-shell">
        {/* Onboarding Modal */}
        {showOnboarding && (
          <OnboardingModal
            onClose={() => setShowOnboarding(false)}
            onCloudConsent={handleCloudConsent}
          />
        )}

        {/* Sidebar */}
        <aside className="sidebar">
          <div className="sidebar-logo">
            <div className="logo-icon">🤖</div>
            <div className="logo-text">
              <h1>Tamil AI</h1>
              <span>Hybrid AI · Local + Cloud</span>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
            <div className="nav-section-label">Navigation</div>
            {NAV_ITEMS.map(item => (
              <button
                key={item.id}
                id={`nav-${item.id}`}
                className={`nav-item ${activeView === item.id ? 'active' : ''}`}
                onClick={() => setActiveView(item.id)}
              >
                <span>{item.icon}</span>
                <span>{item.label}</span>
              </button>
            ))}
          </div>

          {/* Runtime quick-status in sidebar */}
          <div style={{ marginTop: '1rem' }}>
            <div className="nav-section-label">AI Runtime</div>
            <div style={{
              padding: '0.65rem 0.75rem',
              borderRadius: 'var(--radius-md)',
              background: 'var(--color-surface-2)',
              border: '1px solid var(--color-border)',
              fontSize: '0.78rem',
              display: 'flex', flexDirection: 'column', gap: '0.35rem',
            }}>
              <SidebarRuntimeRow label="Mode"   value={runtimeData?.mode?.toUpperCase() || '…'} />
              <SidebarRuntimeRow
                label="Local"
                value={runtimeData ? (runtimeData.local_available ? '🟢 Online' : '🔴 Offline') : '…'}
              />
              <SidebarRuntimeRow
                label="Cloud"
                value={runtimeData ? (runtimeData.cloud_available ? '🟢 Online' : '⚫ None') : '…'}
              />
              <SidebarRuntimeRow label="Model"  value={runtimeData?.active_model || '…'} />
            </div>
          </div>

          <div style={{ marginTop: 'auto', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            <div className="nav-section-label">System</div>
            <div style={{
              padding: '0.75rem',
              borderRadius: 'var(--radius-md)',
              background: 'var(--color-surface-2)',
              border: '1px solid var(--color-border)',
              fontSize: '0.8rem',
            }}>
              <div style={{ color: 'var(--color-text-muted)', marginBottom: '0.5rem' }}>Session ID</div>
              <div style={{
                fontFamily: 'monospace',
                color: 'var(--color-accent-light)',
                fontSize: '0.7rem',
                wordBreak: 'break-all',
              }}>
                {sessionId.slice(0, 20)}…
              </div>
            </div>
          </div>

          <div className="sidebar-footer">
            Tamil AI Assistant v4.0<br />
            <span style={{ fontSize: '0.65rem' }}>Powered by Ollama + FastAPI</span>
          </div>
        </aside>

        {/* Main */}
        <div className="main-content">
          <header className="topbar">
            <div className="topbar-title">
              {activeView === 'chat'   ? '💬 Chat'
               : activeView === 'memory' ? '🧠 Persistent Memory'
               : '⚙️ Admin Panel'}
            </div>
            {/* Phase 4: Runtime controls in topbar */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <ModelSelector onChange={setSelectedModel} />
              <RuntimeWidget onRuntimeChange={handleRuntimeChange} />
              <div className={`status-badge ${ollamaAlive === true ? 'online' : 'offline'}`}>
                <div className="status-dot" />
                {ollamaAlive === null ? 'Checking…'
                 : ollamaAlive ? 'Local AI Online'
                 : runtimeData?.cloud_available ? 'Cloud AI Active'
                 : 'AI Offline'}
              </div>
            </div>
          </header>

          {activeView === 'chat'   && <ChatView sessionId={sessionId} />}
          {activeView === 'memory' && <MemoryPanel sessionId={sessionId} />}
          {activeView === 'admin'  && <AdminView />}
        </div>
      </div>
    </RuntimeContext.Provider>
  );
}

function SidebarRuntimeRow({ label, value }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <span style={{ color: 'var(--color-text-faint)', fontSize: '0.72rem' }}>{label}</span>
      <span style={{ color: 'var(--color-text-muted)', fontWeight: 500, fontSize: '0.72rem' }}>{value}</span>
    </div>
  );
}
