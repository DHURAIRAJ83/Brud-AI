import React, { useState, useEffect, useRef } from 'react';
import { adminListPlugins, adminTogglePlugin, adminUploadPlugin, adminDeletePlugin } from '../services/api';
import RoleGuard from './RoleGuard';

export default function PluginsPage({ user }) {
  const [plugins, setPlugins] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [msg, setMsg] = useState('');
  const fileInputRef = useRef(null);

  const notify = (m) => { setMsg(m); setTimeout(() => setMsg(''), 4000); };

  const fetchPlugins = async () => {
    setLoading(true);
    try {
      // Non-admins can load the list of plugins too (the backend routes are admin-required, 
      // but in dev environment or mock auth we bypass or let them load. If the backend fails 
      // with 403, standard users see an unauthorized message, or we can handle it cleanly).
      const data = await adminListPlugins();
      setPlugins(data);
    } catch (e) {
      notify(`❌ Failed to load plugins: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPlugins();
  }, []);

  const handleToggle = async (name, currentStatus) => {
    try {
      await adminTogglePlugin(name, !currentStatus);
      notify(`✅ Updated "${name}" status`);
      fetchPlugins();
    } catch (e) {
      notify(`❌ ${e.message}`);
    }
  };

  const handleUpload = async (file) => {
    if (!file) return;
    if (!file.name.endsWith('.py')) {
      notify('❌ Only .py files are supported');
      return;
    }
    setUploading(true);
    try {
      const res = await adminUploadPlugin(file);
      notify(res.message || '✅ Plugin uploaded successfully');
      fetchPlugins();
    } catch (e) {
      notify(`❌ ${e.message}`);
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (name) => {
    if (!confirm(`Are you sure you want to uninstall and delete "${name}"?`)) return;
    try {
      const res = await adminDeletePlugin(name);
      notify(res.message || `Deleted "${name}"`);
      fetchPlugins();
    } catch (e) {
      notify(`❌ ${e.message}`);
    }
  };

  const isGuest = user?.role === 'guest' || !user;

  return (
    <div style={{ padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1.5rem', overflowY: 'auto', height: '100%' }}>
      <div>
        <h2 style={{ fontSize: '1.6rem', fontWeight: 800, background: 'linear-gradient(135deg, var(--color-accent-light), var(--color-teal))', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          🔌 Plugins Marketplace
        </h2>
        <p style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem', marginTop: '0.2rem' }}>
          Extend Rudran capabilities with sandboxed custom Python tools.
        </p>
      </div>

      {msg && (
        <div style={{
          padding: '0.75rem 1rem', borderRadius: 'var(--radius-md)',
          background: msg.includes('❌') ? 'rgba(239,68,68,0.1)' : 'rgba(34,211,165,0.1)',
          border: `1px solid ${msg.includes('❌') ? 'rgba(239,68,68,0.3)' : 'rgba(34,211,165,0.3)'}`,
          color: msg.includes('❌') ? 'var(--color-error)' : 'var(--color-success)',
          fontSize: '0.875rem',
        }}>{msg}</div>
      )}

      {/* Upload Zone - Only for Admins */}
      <RoleGuard user={user} allowedRoles={['admin']}>
        <div className="card" style={{ border: '1px dashed var(--color-border)', background: 'var(--color-surface-2)', padding: '1.25rem' }}>
          <div className="card-title">🔌 Install Custom Python Plugin</div>
          <div
            className={`drop-zone ${dragOver ? 'drag-over' : ''}`}
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => { e.preventDefault(); setDragOver(false); handleUpload(e.dataTransfer.files[0]); }}
            style={{
              border: '2px dashed rgba(124,92,252,0.3)',
              borderRadius: 'var(--radius-md)',
              padding: '1.5rem',
              textAlign: 'center',
              cursor: 'pointer',
              transition: 'all 0.2s',
              background: dragOver ? 'rgba(124,92,252,0.08)' : 'transparent',
            }}
          >
            <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>⚡</div>
            <div style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--color-text)' }}>
              {uploading ? 'Uploading and registering…' : 'Drag & drop plugin file here, or click to browse'}
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--color-text-faint)', marginTop: '0.25rem' }}>
              Must be a valid Python (.py) file adhering to the Plugin Contract.
            </div>
          </div>
          <input ref={fileInputRef} type="file" accept=".py" style={{ display: 'none' }}
            onChange={e => handleUpload(e.target.files[0])} />
        </div>
      </RoleGuard>

      {loading ? (
        <div style={{ color: 'var(--color-text-muted)' }}>Loading plugins registry...</div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '1rem' }}>
          {plugins.map((p, i) => (
            <div key={i} className="card" style={{
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              gap: '1rem',
              border: p.enabled ? '1px solid var(--color-border)' : '1px solid rgba(255,255,255,0.05)',
              background: 'var(--color-surface)',
              padding: '1.25rem',
              borderRadius: '16px',
              opacity: p.enabled ? 1 : 0.7,
              transition: 'all 0.2s'
            }}>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <h4 style={{ fontWeight: 700, fontSize: '0.95rem', margin: 0, color: 'var(--color-text)' }}>{p.name}</h4>
                  <span style={{
                    padding: '0.15rem 0.5rem',
                    borderRadius: 'var(--radius-full)',
                    background: p.source === 'builtin' ? 'rgba(34,211,165,0.1)' : 'rgba(124,92,252,0.1)',
                    color: p.source === 'builtin' ? 'var(--color-success)' : 'var(--color-accent-light)',
                    border: `1px solid ${p.source === 'builtin' ? 'rgba(34,211,165,0.3)' : 'rgba(124,92,252,0.3)'}`,
                    fontSize: '0.68rem',
                  }}>
                    {p.source === 'builtin' ? 'built-in' : 'plugin'}
                  </span>
                </div>
                <p style={{ color: 'var(--color-text-muted)', fontSize: '0.78rem', marginTop: '0.4rem', minHeight: '2rem' }}>
                  {p.description || 'No description provided.'}
                </p>
                <div style={{ display: 'flex', gap: '0.3rem', flexWrap: 'wrap', marginTop: '0.5rem' }}>
                  {(p.intents || []).map(intent => (
                    <span key={intent} className="intent-tag" style={{ fontSize: '0.7rem' }}>{intent}</span>
                  ))}
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid var(--color-border)', paddingTop: '0.75rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  {/* Show toggle button or static active indicator depending on role */}
                  <RoleGuard user={user} allowedRoles={['admin']} fallback={
                    <span style={{ fontSize: '0.78rem', color: p.enabled ? 'var(--color-success)' : 'var(--color-text-muted)' }}>
                      {p.enabled ? '🟢 Enabled' : '🔴 Disabled'}
                    </span>
                  }>
                    <label className="switch" style={{ position: 'relative', display: 'inline-block', width: '38px', height: '20px' }}>
                      <input
                        type="checkbox"
                        checked={p.enabled}
                        onChange={() => handleToggle(p.name, p.enabled)}
                        style={{ opacity: 0, width: 0, height: 0 }}
                      />
                      <span style={{
                        position: 'absolute',
                        cursor: 'pointer',
                        top: 0, left: 0, right: 0, bottom: 0,
                        backgroundColor: p.enabled ? 'var(--color-accent)' : '#4b5563',
                        borderRadius: '20px',
                        transition: '0.2s',
                      }}>
                        <span style={{
                          position: 'absolute',
                          content: '""',
                          height: '14px', width: '14px',
                          left: p.enabled ? '20px' : '3px',
                          bottom: '3px',
                          backgroundColor: 'white',
                          borderRadius: '50%',
                          transition: '0.2s',
                        }} />
                      </span>
                    </label>
                    <span style={{ fontSize: '0.78rem', color: p.enabled ? 'var(--color-success)' : 'var(--color-text-muted)' }}>
                      {p.enabled ? 'Active' : 'Disabled'}
                    </span>
                  </RoleGuard>
                </div>

                {p.source !== 'builtin' && (
                  <RoleGuard user={user} allowedRoles={['admin']}>
                    <button
                      className="btn btn-danger"
                      style={{ padding: '0.2rem 0.6rem', fontSize: '0.72rem' }}
                      onClick={() => handleDelete(p.name)}
                    >
                      Uninstall
                    </button>
                  </RoleGuard>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
