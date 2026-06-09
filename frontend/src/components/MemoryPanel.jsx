import React, { useState, useEffect, useCallback } from 'react';
import {
  getMemories,
  saveMemory,
  deleteMemory,
  deleteAllMemories,
  searchMemory,
} from '../services/api';

const CATEGORIES = [
  { id: 'all',               label: 'All',            icon: '🧠', color: '#818cf8' },
  { id: 'user_fact',         label: 'User Facts',     icon: '👤', color: '#34d399' },
  { id: 'preference',        label: 'Preferences',    icon: '⚙️', color: '#f59e0b' },
  { id: 'long_term_context', label: 'Long-term',      icon: '📌', color: '#f472b6' },
];

const CATEGORY_COLORS = {
  user_fact:         { bg: 'rgba(52,211,153,0.12)',  border: '#34d399', text: '#34d399' },
  preference:        { bg: 'rgba(245,158,11,0.12)',  border: '#f59e0b', text: '#f59e0b' },
  long_term_context: { bg: 'rgba(244,114,182,0.12)', border: '#f472b6', text: '#f472b6' },
};

function MemoryCard({ fact, onDelete }) {
  const [deleting, setDeleting] = useState(false);
  const clr = CATEGORY_COLORS[fact.category] || CATEGORY_COLORS.user_fact;
  const catInfo = CATEGORIES.find(c => c.id === fact.category);

  async function handleDelete() {
    setDeleting(true);
    try { await onDelete(fact.id); }
    finally { setDeleting(false); }
  }

  const date = new Date(fact.updated_at * 1000).toLocaleString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });

  return (
    <div style={{
      background: clr.bg,
      border: `1px solid ${clr.border}`,
      borderRadius: '12px',
      padding: '0.875rem 1rem',
      display: 'flex',
      flexDirection: 'column',
      gap: '0.4rem',
      position: 'relative',
      animation: 'fadeIn 0.25s ease',
    }}>
      {/* Category badge */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{
          fontSize: '0.68rem', fontWeight: 700, letterSpacing: '0.07em',
          color: clr.text, background: `${clr.border}22`,
          padding: '2px 8px', borderRadius: '999px', textTransform: 'uppercase',
        }}>
          {catInfo?.icon} {catInfo?.label || fact.category}
        </span>
        <button
          id={`delete-fact-${fact.id}`}
          onClick={handleDelete}
          disabled={deleting}
          title="Delete this memory"
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: '#ef4444', fontSize: '0.85rem', opacity: deleting ? 0.5 : 0.7,
            transition: 'opacity 0.2s', padding: '2px 6px', borderRadius: '6px',
          }}
          onMouseEnter={e => e.target.style.opacity = 1}
          onMouseLeave={e => e.target.style.opacity = deleting ? 0.5 : 0.7}
        >
          {deleting ? '…' : '🗑'}
        </button>
      </div>

      {/* Key + Value */}
      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'baseline', flexWrap: 'wrap' }}>
        <span style={{
          fontWeight: 600, fontSize: '0.82rem',
          color: 'var(--color-text-muted)', minWidth: '80px',
        }}>
          {fact.key}
        </span>
        <span style={{
          fontSize: '0.95rem', color: 'var(--color-text)',
          fontWeight: 500, wordBreak: 'break-word',
        }}>
          {fact.value}
        </span>
      </div>

      {/* Meta */}
      <div style={{ display: 'flex', gap: '0.75rem', fontSize: '0.67rem', color: 'var(--color-text-muted)', marginTop: '0.1rem' }}>
        <span>{fact.source === 'auto_extracted' ? '🤖 Auto' : '✋ Manual'}</span>
        <span>Confidence: {Math.round(fact.confidence * 100)}%</span>
        <span>Updated: {date}</span>
      </div>
    </div>
  );
}

function AddMemoryForm({ userId, onSaved }) {
  const [key, setKey]     = useState('');
  const [value, setValue] = useState('');
  const [cat, setCat]     = useState('user_fact');
  const [saving, setSaving] = useState(false);
  const [error, setError]   = useState('');

  async function handleSubmit(e) {
    e.preventDefault();
    if (!key.trim() || !value.trim()) return;
    setSaving(true); setError('');
    try {
      await saveMemory(userId, key.trim(), value.trim(), cat);
      setKey(''); setValue('');
      onSaved();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} style={{
      background: 'var(--color-surface-2)',
      border: '1px solid var(--color-border)',
      borderRadius: '14px',
      padding: '1rem 1.25rem',
      display: 'flex',
      flexDirection: 'column',
      gap: '0.75rem',
    }}>
      <div style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--color-accent-light)' }}>
        ➕ Add Memory
      </div>
      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
        <select
          id="memory-category-select"
          value={cat}
          onChange={e => setCat(e.target.value)}
          style={{
            background: 'var(--color-surface)', border: '1px solid var(--color-border)',
            color: 'var(--color-text)', borderRadius: '8px', padding: '0.45rem 0.6rem',
            fontSize: '0.8rem', cursor: 'pointer',
          }}
        >
          {CATEGORIES.filter(c => c.id !== 'all').map(c => (
            <option key={c.id} value={c.id}>{c.icon} {c.label}</option>
          ))}
        </select>
        <input
          id="memory-key-input"
          type="text"
          placeholder="Key (e.g. name, city)"
          value={key}
          onChange={e => setKey(e.target.value)}
          style={{
            flex: 1, minWidth: '100px',
            background: 'var(--color-surface)', border: '1px solid var(--color-border)',
            color: 'var(--color-text)', borderRadius: '8px', padding: '0.45rem 0.75rem',
            fontSize: '0.85rem',
          }}
        />
        <input
          id="memory-value-input"
          type="text"
          placeholder="Value (e.g. Dhurairaj)"
          value={value}
          onChange={e => setValue(e.target.value)}
          style={{
            flex: 2, minWidth: '140px',
            background: 'var(--color-surface)', border: '1px solid var(--color-border)',
            color: 'var(--color-text)', borderRadius: '8px', padding: '0.45rem 0.75rem',
            fontSize: '0.85rem',
          }}
        />
        <button
          id="memory-save-btn"
          type="submit"
          disabled={saving || !key.trim() || !value.trim()}
          style={{
            background: 'var(--color-accent)', color: '#fff',
            border: 'none', borderRadius: '8px',
            padding: '0.45rem 1rem', fontWeight: 600,
            fontSize: '0.85rem', cursor: 'pointer',
            opacity: saving ? 0.6 : 1, transition: 'opacity 0.2s',
          }}
        >
          {saving ? 'Saving…' : 'Save'}
        </button>
      </div>
      {error && (
        <div style={{ fontSize: '0.78rem', color: '#ef4444' }}>⚠️ {error}</div>
      )}
    </form>
  );
}

export default function MemoryPanel({ sessionId }) {
  const userId = sessionId;

  const [memories, setMemories]   = useState([]);
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState('');
  const [activeTab, setActiveTab] = useState('all');
  const [searchQ, setSearchQ]     = useState('');
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState(null); // null = no search active

  // Load memories
  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const cat = activeTab === 'all' ? null : activeTab;
      const data = await getMemories(userId, cat);
      setMemories(data.memories || []);
      setSearchResults(null);
      setSearchQ('');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [userId, activeTab]);

  useEffect(() => { load(); }, [load]);

  // Search
  async function handleSearch(e) {
    e.preventDefault();
    if (!searchQ.trim()) { setSearchResults(null); return; }
    setSearching(true);
    try {
      const data = await searchMemory(userId, searchQ.trim());
      setSearchResults(data.results || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setSearching(false);
    }
  }

  function clearSearch() { setSearchResults(null); setSearchQ(''); }

  // Delete single
  async function handleDelete(factId) {
    await deleteMemory(userId, factId);
    setMemories(prev => prev.filter(m => m.id !== factId));
    if (searchResults) setSearchResults(prev => prev.filter(m => m.id !== factId));
  }

  // Delete all
  async function handleDeleteAll() {
    if (!window.confirm('Delete ALL memories for this session? This cannot be undone.')) return;
    await deleteAllMemories(userId);
    setMemories([]);
    setSearchResults(null);
  }

  const displayList = searchResults !== null ? searchResults : memories;

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', gap: '1rem',
      height: '100%', overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 700, color: 'var(--color-text)' }}>
            🧠 Persistent Memory
          </h2>
          <p style={{ margin: '0.2rem 0 0', fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
            {memories.length} memories stored · Session: {userId.slice(0, 12)}…
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            id="memory-refresh-btn"
            onClick={load}
            style={{
              background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
              color: 'var(--color-text)', borderRadius: '8px', padding: '0.4rem 0.75rem',
              fontSize: '0.8rem', cursor: 'pointer',
            }}
          >
            🔄 Refresh
          </button>
          {memories.length > 0 && (
            <button
              id="memory-delete-all-btn"
              onClick={handleDeleteAll}
              style={{
                background: 'rgba(239,68,68,0.1)', border: '1px solid #ef4444',
                color: '#ef4444', borderRadius: '8px', padding: '0.4rem 0.75rem',
                fontSize: '0.8rem', cursor: 'pointer',
              }}
            >
              🗑 Clear All
            </button>
          )}
        </div>
      </div>

      {/* Category Tabs */}
      <div style={{ display: 'flex', gap: '0.4rem', flexShrink: 0, flexWrap: 'wrap' }}>
        {CATEGORIES.map(cat => (
          <button
            key={cat.id}
            id={`memory-tab-${cat.id}`}
            onClick={() => { setActiveTab(cat.id); setSearchResults(null); setSearchQ(''); }}
            style={{
              background: activeTab === cat.id ? cat.color : 'var(--color-surface-2)',
              color: activeTab === cat.id ? '#fff' : 'var(--color-text-muted)',
              border: `1px solid ${activeTab === cat.id ? cat.color : 'var(--color-border)'}`,
              borderRadius: '999px', padding: '0.35rem 0.9rem',
              fontSize: '0.78rem', fontWeight: 600, cursor: 'pointer',
              transition: 'all 0.2s',
            }}
          >
            {cat.icon} {cat.label}
          </button>
        ))}
      </div>

      {/* Search Bar */}
      <form onSubmit={handleSearch} style={{ display: 'flex', gap: '0.5rem', flexShrink: 0 }}>
        <input
          id="memory-search-input"
          type="text"
          placeholder="Search memories… (e.g. name, Tamil)"
          value={searchQ}
          onChange={e => setSearchQ(e.target.value)}
          style={{
            flex: 1,
            background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
            color: 'var(--color-text)', borderRadius: '10px', padding: '0.5rem 0.9rem',
            fontSize: '0.85rem',
          }}
        />
        <button
          id="memory-search-btn"
          type="submit"
          disabled={searching}
          style={{
            background: 'var(--color-accent)', color: '#fff',
            border: 'none', borderRadius: '10px',
            padding: '0.5rem 1rem', fontWeight: 600,
            fontSize: '0.82rem', cursor: 'pointer',
          }}
        >
          {searching ? '…' : '🔍'}
        </button>
        {searchResults !== null && (
          <button
            id="memory-search-clear-btn"
            type="button"
            onClick={clearSearch}
            style={{
              background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
              color: 'var(--color-text-muted)', borderRadius: '10px',
              padding: '0.5rem 0.75rem', fontSize: '0.82rem', cursor: 'pointer',
            }}
          >
            ✕
          </button>
        )}
      </form>

      {/* Add Memory Form */}
      <div style={{ flexShrink: 0 }}>
        <AddMemoryForm userId={userId} onSaved={load} />
      </div>

      {/* Error */}
      {error && (
        <div style={{
          background: 'rgba(239,68,68,0.1)', border: '1px solid #ef4444',
          borderRadius: '10px', padding: '0.6rem 1rem',
          fontSize: '0.82rem', color: '#ef4444', flexShrink: 0,
        }}>
          ⚠️ {error}
        </div>
      )}

      {/* Search label */}
      {searchResults !== null && (
        <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', flexShrink: 0 }}>
          🔍 Showing {searchResults.length} result{searchResults.length !== 1 ? 's' : ''} for "{searchQ}"
        </div>
      )}

      {/* Memory List */}
      <div style={{
        flex: 1, overflowY: 'auto',
        display: 'flex', flexDirection: 'column', gap: '0.6rem',
        paddingRight: '0.25rem',
      }}>
        {loading ? (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            flex: 1, color: 'var(--color-text-muted)', fontSize: '0.9rem', gap: '0.5rem',
          }}>
            <span style={{ animation: 'spin 1s linear infinite', display: 'inline-block' }}>⏳</span>
            Loading memories…
          </div>
        ) : displayList.length === 0 ? (
          <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            justifyContent: 'center', flex: 1, gap: '0.75rem',
            color: 'var(--color-text-muted)',
          }}>
            <div style={{ fontSize: '2.5rem' }}>🧠</div>
            <div style={{ fontSize: '0.9rem', fontWeight: 600 }}>No memories yet</div>
            <div style={{ fontSize: '0.78rem', textAlign: 'center', maxWidth: '260px', lineHeight: 1.6 }}>
              Start chatting — facts like your name, preferences, and interests are automatically extracted and stored here.
            </div>
          </div>
        ) : (
          displayList.map(fact => (
            <MemoryCard key={fact.id} fact={fact} onDelete={handleDelete} />
          ))
        )}
      </div>

      <style>{`
        @keyframes fadeIn { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:translateY(0); } }
        @keyframes spin   { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
