import React, { useState } from 'react';

const BASE = window.location.origin + '/api';

async function apiPost(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data;
}

export default function AuthPage({ onLogin }) {
  const [mode, setMode]       = useState('login'); // 'login' | 'register'
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [email, setEmail]     = useState('');
  const [displayName, setDisplayName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (mode === 'login') {
        const data = await apiPost('/auth/login', { username, password });
        localStorage.setItem('auth_token', data.access_token);
        localStorage.setItem('auth_user', JSON.stringify(data.user));
        if (data.csrf_token) {
          localStorage.setItem('csrf_token', data.csrf_token);
        }
        onLogin(data.user, data.access_token);
      } else {
        await apiPost('/auth/register', {
          username, password,
          email: email || undefined,
          display_name: displayName || undefined,
        });
        // Auto-login after register
        const data = await apiPost('/auth/login', { username, password });
        localStorage.setItem('auth_token', data.access_token);
        localStorage.setItem('auth_user', JSON.stringify(data.user));
        if (data.csrf_token) {
          localStorage.setItem('csrf_token', data.csrf_token);
        }
        onLogin(data.user, data.access_token);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      background: 'var(--color-bg)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '1rem',
    }}>
      <div style={{
        width: '100%',
        maxWidth: '420px',
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: '20px',
        padding: '2.5rem',
        boxShadow: '0 32px 80px rgba(0,0,0,0.5)',
        animation: 'fadeInUp 0.4s ease',
      }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <div style={{ fontSize: '3rem', marginBottom: '0.5rem', animation: 'pulse 3s infinite' }}>🤖</div>
          <h1 style={{ margin: 0, fontSize: '1.6rem', fontWeight: 800, background: 'linear-gradient(135deg,#a78bfa,#22d3ee)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
            Tamil AI
          </h1>
          <p style={{ margin: '0.3rem 0 0', color: 'var(--color-text-muted)', fontSize: '0.82rem' }}>
            {mode === 'login' ? 'Sign in to your account' : 'Create a new account'}
          </p>
        </div>

        {/* Tab switcher */}
        <div style={{
          display: 'flex', borderRadius: '10px',
          background: 'var(--color-surface-2)',
          padding: '4px', marginBottom: '1.5rem',
        }}>
          {['login', 'register'].map(tab => (
            <button
              key={tab}
              onClick={() => { setMode(tab); setError(''); }}
              style={{
                flex: 1, padding: '0.5rem',
                borderRadius: '8px',
                border: 'none', cursor: 'pointer',
                fontFamily: 'inherit', fontWeight: 600, fontSize: '0.85rem',
                transition: 'all 0.2s',
                background: mode === tab ? 'var(--color-accent)' : 'transparent',
                color: mode === tab ? '#fff' : 'var(--color-text-muted)',
              }}
            >
              {tab === 'login' ? '🔑 Sign In' : '✨ Register'}
            </button>
          ))}
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {mode === 'register' && (
            <>
              <InputField
                id="auth-display-name"
                label="Display Name"
                placeholder="Your name"
                value={displayName}
                onChange={setDisplayName}
                type="text"
              />
              <InputField
                id="auth-email"
                label="Email (optional)"
                placeholder="your@email.com"
                value={email}
                onChange={setEmail}
                type="email"
              />
            </>
          )}
          <InputField
            id="auth-username"
            label="Username"
            placeholder="Enter username"
            value={username}
            onChange={setUsername}
            type="text"
            required
          />
          <InputField
            id="auth-password"
            label="Password"
            placeholder={mode === 'register' ? 'At least 6 characters' : 'Enter password'}
            value={password}
            onChange={setPassword}
            type="password"
            required
          />

          {error && (
            <div style={{
              padding: '0.65rem 0.85rem',
              background: 'rgba(239,68,68,0.1)',
              border: '1px solid rgba(239,68,68,0.3)',
              borderRadius: '8px',
              color: '#f87171',
              fontSize: '0.82rem',
            }}>
              ⚠️ {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              padding: '0.85rem',
              borderRadius: '10px',
              border: 'none',
              background: 'linear-gradient(135deg,#7c5cfc,#a78bfa)',
              color: '#fff',
              fontWeight: 700,
              fontSize: '0.95rem',
              cursor: loading ? 'not-allowed' : 'pointer',
              fontFamily: 'inherit',
              opacity: loading ? 0.7 : 1,
              transition: 'all 0.2s',
              marginTop: '0.25rem',
            }}
          >
            {loading ? '⏳ Please wait…' : mode === 'login' ? '🚀 Sign In' : '✨ Create Account'}
          </button>
        </form>

        {/* Guest mode */}
        <div style={{ textAlign: 'center', marginTop: '1.5rem' }}>
          <button
            onClick={() => onLogin(null, null)}
            style={{
              background: 'none', border: 'none',
              color: 'var(--color-text-faint)',
              fontSize: '0.78rem', cursor: 'pointer',
              fontFamily: 'inherit',
              textDecoration: 'underline',
              textUnderlineOffset: '3px',
            }}
          >
            Continue as guest →
          </button>
        </div>
      </div>

      <style>{`
        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(20px); }
          to   { opacity: 1; transform: none; }
        }
        @keyframes pulse {
          0%,100% { transform: scale(1); }
          50%      { transform: scale(1.08); }
        }
      `}</style>
    </div>
  );
}

function InputField({ id, label, placeholder, value, onChange, type = 'text', required = false }) {
  return (
    <div>
      <label htmlFor={id} style={{
        display: 'block', fontSize: '0.78rem', fontWeight: 600,
        color: 'var(--color-text-muted)', marginBottom: '0.4rem',
        letterSpacing: '0.02em',
      }}>
        {label}
      </label>
      <input
        id={id}
        type={type}
        placeholder={placeholder}
        value={value}
        onChange={e => onChange(e.target.value)}
        required={required}
        style={{
          width: '100%',
          padding: '0.7rem 0.9rem',
          borderRadius: '10px',
          border: '1px solid var(--color-border)',
          background: 'var(--color-surface-2)',
          color: 'var(--color-text)',
          fontFamily: 'inherit',
          fontSize: '0.9rem',
          boxSizing: 'border-box',
          outline: 'none',
          transition: 'border-color 0.2s',
        }}
        onFocus={e => e.target.style.borderColor = 'var(--color-accent)'}
        onBlur={e => e.target.style.borderColor = 'var(--color-border)'}
      />
    </div>
  );
}
