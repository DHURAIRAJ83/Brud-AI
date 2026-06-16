import React, { useState, useEffect, useRef, createContext, useContext, useCallback } from 'react';
import ChatView from './components/ChatView';
import AdminView from './components/AdminView';
import MemoryPanel from './components/MemoryPanel';
import ConversationsView from './components/ConversationsView';
import AuthPage from './components/AuthPage';
import RuntimeWidget from './components/RuntimeWidget';
import ModelSelector, { getSelectedModel } from './components/ModelSelector';
import OnboardingModal from './components/OnboardingModal';
import { systemStatus, getRuntimeStatus, authLogout } from './services/api';

// New components & sub-pages
import HomePage from './components/HomePage';
import SkillsPage from './components/SkillsPage';
import PluginsPage from './components/PluginsPage';
import AutomationPage from './components/AutomationPage';
import DownloadsPage from './components/DownloadsPage';
import DocsPage from './components/DocsPage';
import VoiceSecurityPanel from './components/VoiceSecurityPanel';
import { ThemeProvider, ThemeSwitcher } from './components/ThemeProvider';
import RoleGuard from './components/RoleGuard';

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
  { id: 'chat',          label: 'Chat Workspace', icon: '💬' },
  { id: 'conversations', label: 'Conversations',  icon: '🗒️' },
  { id: 'memory',        label: 'Memory Engine',  icon: '🧠' },
  { id: 'skills',        label: 'Skills Store',   icon: '🎯' },
  { id: 'plugins',       label: 'Plugins Registry',icon: '🔌' },
  { id: 'automation',    label: 'Automation',     icon: '⚙️' },
  { id: 'voice',         label: 'Voice Security', icon: '🔒' },
  { id: 'downloads',     label: 'Downloads',      icon: '⬇️' },
  { id: 'docs',          label: 'Documentation',  icon: '📚' },
];

function AppContent() {
  const [activeView, setActiveView]     = useState(() => {
    const path = window.location.pathname;
    if (path === '/chat') return 'chat';
    if (path === '/admin') return 'admin';
    if (path === '/skills') return 'skills';
    if (path === '/plugins') return 'plugins';
    if (path === '/automation') return 'automation';
    if (path === '/downloads') return 'downloads';
    if (path === '/docs') return 'docs';
    return 'home';
  });

  const [ollamaAlive, setOllamaAlive]   = useState(null);
  const [runtimeData, setRuntimeData]   = useState(null);
  const [selectedModel, setSelectedModel] = useState(() => getSelectedModel());
  const [showOnboarding, setShowOnboarding] = useState(false);
  const sessionId = useRef(getSessionId()).current;

  // Auth State
  const [authUser, setAuthUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem('auth_user') || 'null'); } catch { return null; }
  });
  const [authChecked, setAuthChecked] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('auth_token');
    const user  = localStorage.getItem('auth_user');
    if (token && user) {
      try { setAuthUser(JSON.parse(user)); } catch {}
    }
    setAuthChecked(true);
  }, []);

  useEffect(() => {
    const handleAuthLogout = () => {
      setAuthUser(undefined);
      navigate('home');
    };
    window.addEventListener('auth-logout', handleAuthLogout);
    return () => window.removeEventListener('auth-logout', handleAuthLogout);
  }, []);

  const navigate = (view) => {
    // Auth Gates & Dashboard redirects
    if (view === 'chat' && !authUser) {
      // Force Login/AuthPage representation first
      setAuthUser(undefined);
    }
    
    setActiveView(view);
    const path = view === 'home' ? '/' : `/${view}`;
    window.history.pushState(null, '', path);
  };

  useEffect(() => {
    const handlePopState = () => {
      const path = window.location.pathname;
      if (path === '/chat') setActiveView('chat');
      else if (path === '/admin') setActiveView('admin');
      else if (path === '/skills') setActiveView('skills');
      else if (path === '/plugins') setActiveView('plugins');
      else if (path === '/automation') setActiveView('automation');
      else if (path === '/downloads') setActiveView('downloads');
      else if (path === '/docs') setActiveView('docs');
      else setActiveView('home');
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const handleLogin = (user, token) => {
    setAuthUser(user); // null = guest mode
    setAuthChecked(true);
    if (user && user.role === 'admin') {
      navigate('admin');
    } else {
      navigate('chat');
    }
  };

  const handleLogout = async () => {
    try {
      await authLogout();
    } catch (err) {
      console.warn("Backend logout failed", err);
    }
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_user');
    localStorage.removeItem('csrf_token');
    setAuthUser(undefined); // forces redirect to AuthPage
    navigate('home');
  };

  // Initial runtime check
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

  if (!authChecked) return null;

  // Landing Page layout view
  if (activeView === 'home') {
    return (
      <HomePage 
        authUser={authUser} 
        onStartChat={() => navigate('chat')} 
        onNavigate={navigate} 
      />
    );
  }

  // Auth Gate check
  if (authUser === undefined) {
    return <AuthPage onLogin={handleLogin} />;
  }

  return (
    <RuntimeContext.Provider value={runtimeCtx}>
      <div className="app-shell">
        {showOnboarding && (
          <OnboardingModal
            onClose={() => setShowOnboarding(false)}
            onCloudConsent={handleCloudConsent}
          />
        )}

        {/* Sidebar */}
        <aside className="sidebar">
          <div className="sidebar-logo" style={{ cursor: 'pointer' }} onClick={() => navigate('home')}>
            <div className="logo-icon">🤖</div>
            <div className="logo-text">
              <h1>Rudran AI</h1>
              <span>Tamil Native Assistant</span>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
            <div className="nav-section-label">Navigation</div>
            {NAV_ITEMS.map(item => (
              <button
                key={item.id}
                id={`nav-${item.id}`}
                className={`nav-item ${activeView === item.id ? 'active' : ''}`}
                onClick={() => navigate(item.id)}
              >
                <span>{item.icon}</span>
                <span>{item.label}</span>
              </button>
            ))}

            {/* Admin Dashboard view option link (RoleGuarded) */}
            <RoleGuard user={authUser} allowedRoles={['admin']}>
              <button
                id="nav-admin"
                className={`nav-item ${activeView === 'admin' ? 'active' : ''}`}
                onClick={() => navigate('admin')}
                style={{ borderLeft: '3px solid var(--color-accent)' }}
              >
                <span>⚙️</span>
                <span>Operations Center</span>
              </button>
            </RoleGuard>
          </div>

          {/* User Info / Logout */}
          <div style={{ marginTop: 'auto', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <div className="nav-section-label">User Session</div>
            <div style={{
              padding: '0.65rem 0.75rem',
              borderRadius: 'var(--radius-md)',
              background: 'var(--color-surface-2)',
              border: '1px solid var(--color-border)',
              fontSize: '0.78rem',
              display: 'flex', alignItems: 'center', gap: '0.5rem',
            }}>
              <span style={{ fontSize: '1rem' }}>👤</span>
              <span style={{ flex: 1, color: 'var(--color-text-muted)', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {authUser ? (authUser.display_name || authUser.username) : 'Guest User'}
              </span>
              <button
                onClick={handleLogout}
                title="Logout"
                style={{
                  background: 'none', border: 'none', cursor: 'pointer',
                  color: 'var(--color-error)', fontSize: '0.75rem', padding: '2px 6px',
                  borderRadius: '6px', fontFamily: 'inherit',
                }}
              >↩</button>
            </div>
          </div>

          <div className="sidebar-footer">
            Rudran Tamil AI v5.0<br />
            <span style={{ fontSize: '0.65rem' }}>Made for Tamil users</span>
          </div>
        </aside>

        {/* Main Content Area */}
        <div className="main-content">
          <header className="topbar">
            <div className="topbar-title">
              {activeView === 'chat'          ? '💬 Chat Workspace'
               : activeView === 'conversations' ? '🗒️ Conversations'
               : activeView === 'memory'        ? '🧠 Memory Engine'
               : activeView === 'skills'        ? '🎯 Skills Marketplace'
               : activeView === 'plugins'       ? '🔌 Plugins Registry'
               : activeView === 'automation'    ? '⚙️ Automation Center'
               : activeView === 'voice'         ? '🔒 Voice Security'
               : activeView === 'downloads'     ? '⬇️ Downloads'
               : activeView === 'docs'          ? '📚 Documentation'
               : '⚙️ Operations Center'}
            </div>
            
            {/* Theme switcher + Runtime badge in topbar */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
              <ThemeSwitcher />
              
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
            </div>
          </header>

          <div style={{ flex: 1, overflow: 'hidden' }}>
            {activeView === 'chat'          && <ChatView sessionId={sessionId} />}
            {activeView === 'conversations' && <ConversationsView sessionId={sessionId} />}
            {activeView === 'memory'        && <MemoryPanel sessionId={sessionId} />}
            {activeView === 'skills'        && <SkillsPage user={authUser} sessionId={sessionId} />}
            {activeView === 'plugins'       && <PluginsPage user={authUser} />}
            {activeView === 'automation'    && <AutomationPage />}
            {activeView === 'voice'         && <VoiceSecurityPanel user={authUser} />}
            {activeView === 'downloads'     && <DownloadsPage />}
            {activeView === 'docs'          && <DocsPage />}
            {activeView === 'admin'         && <AdminView />}
          </div>
        </div>
      </div>
    </RuntimeContext.Provider>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <AppContent />
    </ThemeProvider>
  );
}
