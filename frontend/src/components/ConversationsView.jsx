import React, { useState, useEffect, useRef, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import {
  listConversations,
  getConversation,
  deleteConversation,
  searchConversations,
  exportConversation
} from '../services/api';

function formatDate(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch { return iso; }
}

function MessageBubble({ turn }) {
  const isUser = turn.role === 'user';
  return (
    <div style={{
      display: 'flex',
      gap: '0.65rem',
      flexDirection: isUser ? 'row-reverse' : 'row',
      marginBottom: '0.75rem',
    }}>
      <div style={{
        width: 32, height: 32, borderRadius: '50%',
        background: isUser ? 'var(--color-accent)' : 'var(--color-surface-2)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: '1rem', flexShrink: 0,
        border: '1px solid var(--color-border)',
      }}>
        {isUser ? '👤' : '🤖'}
      </div>
      <div style={{
        maxWidth: '75%',
        background: isUser ? 'rgba(124,92,252,0.15)' : 'var(--color-surface-2)',
        border: `1px solid ${isUser ? 'rgba(124,92,252,0.3)' : 'var(--color-border)'}`,
        borderRadius: isUser ? '16px 4px 16px 16px' : '4px 16px 16px 16px',
        padding: '0.65rem 0.9rem',
        fontSize: '0.875rem',
        lineHeight: 1.6,
        color: 'var(--color-text)',
      }}>
        <ReactMarkdown>{turn.content}</ReactMarkdown>
        <div style={{ fontSize: '0.65rem', color: 'var(--color-text-faint)', marginTop: '0.3rem', textAlign: isUser ? 'right' : 'left' }}>
          {formatDate(turn.timestamp)}
        </div>
      </div>
    </div>
  );
}

export default function ConversationsView({ sessionId }) {
  const [sessions, setSessions]           = useState([]);
  const [loadingSessions, setLoadingSessions] = useState(true);
  const [selectedSession, setSelectedSession] = useState(null);
  const [turns, setTurns]                 = useState([]);
  const [loadingTurns, setLoadingTurns]   = useState(false);
  const [searchQuery, setSearchQuery]     = useState('');
  const [searchResults, setSearchResults] = useState(null);
  const [searching, setSearching]         = useState(false);
  const [deletingId, setDeletingId]       = useState(null);
  const bottomRef = useRef(null);
  const searchTimeout = useRef(null);

  // Load sessions list
  const loadSessions = useCallback(async () => {
    setLoadingSessions(true);
    try {
      const data = await listConversations();
      setSessions(data.sessions || []);
    } catch (err) {
      console.error('Failed to load sessions:', err);
    } finally {
      setLoadingSessions(false);
    }
  }, []);

  useEffect(() => { loadSessions(); }, [loadSessions]);

  // Load conversation turns
  const selectSession = useCallback(async (sid) => {
    setSelectedSession(sid);
    setSearchResults(null);
    setLoadingTurns(true);
    try {
      const data = await getConversation(sid);
      setTurns(data.turns || []);
    } catch (err) {
      console.error('Failed to load turns:', err);
      setTurns([]);
    } finally {
      setLoadingTurns(false);
    }
  }, []);

  // Auto-scroll when turns change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [turns]);

  // Live search with debounce
  useEffect(() => {
    clearTimeout(searchTimeout.current);
    if (!searchQuery.trim()) { setSearchResults(null); return; }
    searchTimeout.current = setTimeout(async () => {
      setSearching(true);
      try {
        const data = await searchConversations(searchQuery);
        setSearchResults(data.results || []);
      } catch { setSearchResults([]); }
      finally { setSearching(false); }
    }, 400);
  }, [searchQuery]);

  // Delete a session
  const deleteSession = async (sid) => {
    if (!window.confirm('Delete this conversation?')) return;
    setDeletingId(sid);
    try {
      await deleteConversation(sid);
      setSessions(s => s.filter(x => x.session_id !== sid));
      if (selectedSession === sid) { setSelectedSession(null); setTurns([]); }
    } catch (err) { alert('Delete failed: ' + err.message); }
    finally { setDeletingId(null); }
  };

  // Export as JSON
  const exportSession = async (sid) => {
    try {
      const data = await exportConversation(sid);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `conversation_${sid.slice(0, 8)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) { alert('Export failed: ' + err.message); }
  };

  return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* ── Left panel: session list ───────────────────────────── */}
      <div style={{
        width: '320px', flexShrink: 0,
        borderRight: '1px solid var(--color-border)',
        display: 'flex', flexDirection: 'column',
        overflow: 'hidden',
        background: 'var(--color-surface)',
      }}>
        {/* Search bar */}
        <div style={{ padding: '1rem', borderBottom: '1px solid var(--color-border)' }}>
          <div style={{ position: 'relative' }}>
            <span style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', fontSize: '0.85rem', color: 'var(--color-text-faint)' }}>🔍</span>
            <input
              id="conv-search"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Search messages…"
              style={{
                width: '100%', padding: '0.55rem 0.75rem 0.55rem 2.2rem',
                borderRadius: '10px', border: '1px solid var(--color-border)',
                background: 'var(--color-surface-2)', color: 'var(--color-text)',
                fontFamily: 'inherit', fontSize: '0.85rem', boxSizing: 'border-box',
                outline: 'none',
              }}
            />
            {searching && (
              <span style={{ position: 'absolute', right: '0.75rem', top: '50%', transform: 'translateY(-50%)', fontSize: '0.7rem', color: 'var(--color-accent-light)' }}>
                ⏳
              </span>
            )}
          </div>
        </div>

        {/* Results or sessions list */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '0.5rem' }}>
          {searchResults !== null ? (
            <>
              <div style={{ fontSize: '0.72rem', color: 'var(--color-text-faint)', padding: '0.3rem 0.5rem 0.5rem', fontWeight: 600 }}>
                {searchResults.length} result{searchResults.length !== 1 ? 's' : ''} for "{searchQuery}"
              </div>
              {searchResults.length === 0 && (
                <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--color-text-faint)', fontSize: '0.82rem' }}>
                  No messages found.
                </div>
              )}
              {searchResults.map((r, i) => (
                <button
                  key={i}
                  onClick={() => { setSearchQuery(''); selectSession(r.session_id); }}
                  style={{
                    width: '100%', textAlign: 'left',
                    padding: '0.65rem 0.75rem',
                    borderRadius: '10px', border: 'none',
                    background: 'transparent', cursor: 'pointer',
                    fontFamily: 'inherit', marginBottom: '2px',
                    transition: 'background 0.15s',
                  }}
                  onMouseEnter={e => e.currentTarget.style.background = 'var(--color-surface-2)'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                >
                  <div style={{ fontSize: '0.72rem', color: 'var(--color-accent-light)', marginBottom: '0.2rem', fontWeight: 600 }}>
                    {r.role === 'user' ? '👤 You' : '🤖 AI'} · {formatDate(r.timestamp)}
                  </div>
                  <div style={{ fontSize: '0.82rem', color: 'var(--color-text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {r.content}
                  </div>
                  <div style={{ fontSize: '0.65rem', color: 'var(--color-text-faint)', marginTop: '0.2rem' }}>
                    Session: {r.session_id.slice(0, 12)}…
                  </div>
                </button>
              ))}
            </>
          ) : loadingSessions ? (
            <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--color-text-faint)' }}>
              <div style={{ fontSize: '1.5rem', marginBottom: '0.5rem' }}>⏳</div>
              Loading conversations…
            </div>
          ) : sessions.length === 0 ? (
            <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--color-text-faint)', fontSize: '0.85rem' }}>
              <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>💬</div>
              No conversations yet.<br />Start chatting to see history here.
            </div>
          ) : (
            sessions.map(s => (
              <div
                key={s.session_id}
                onClick={() => selectSession(s.session_id)}
                style={{
                  padding: '0.75rem',
                  borderRadius: '10px',
                  background: selectedSession === s.session_id ? 'rgba(124,92,252,0.12)' : 'transparent',
                  border: selectedSession === s.session_id
                    ? '1px solid rgba(124,92,252,0.3)'
                    : '1px solid transparent',
                  cursor: 'pointer',
                  marginBottom: '4px',
                  transition: 'all 0.15s',
                  position: 'relative',
                }}
                onMouseEnter={e => { if (selectedSession !== s.session_id) e.currentTarget.style.background = 'var(--color-surface-2)'; }}
                onMouseLeave={e => { if (selectedSession !== s.session_id) e.currentTarget.style.background = 'transparent'; }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: '0.82rem', color: 'var(--color-text)', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {s.preview || '(empty)'}
                    </div>
                    <div style={{ fontSize: '0.68rem', color: 'var(--color-text-faint)', marginTop: '0.25rem', display: 'flex', gap: '0.5rem' }}>
                      <span>💬 {s.message_count} msgs</span>
                      <span>{formatDate(s.last_at)}</span>
                    </div>
                  </div>
                  {/* Action buttons */}
                  <div style={{ display: 'flex', gap: '2px', marginLeft: '0.5rem', flexShrink: 0 }}
                    onClick={e => e.stopPropagation()}
                  >
                    <button
                      onClick={() => exportSession(s.session_id)}
                      title="Export JSON"
                      style={iconBtnStyle}
                    >⬇️</button>
                    <button
                      onClick={() => deleteSession(s.session_id)}
                      disabled={deletingId === s.session_id}
                      title="Delete"
                      style={{ ...iconBtnStyle, color: '#f87171' }}
                    >🗑️</button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* ── Right panel: conversation replay ──────────────────── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {!selectedSession ? (
          <div style={{
            flex: 1, display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            color: 'var(--color-text-faint)', gap: '0.75rem',
          }}>
            <div style={{ fontSize: '4rem' }}>💬</div>
            <div style={{ fontWeight: 600, fontSize: '1rem', color: 'var(--color-text-muted)' }}>Select a conversation</div>
            <div style={{ fontSize: '0.82rem' }}>Click any session on the left to replay it.</div>
          </div>
        ) : loadingTurns ? (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--color-text-faint)' }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>⏳</div>
              Loading conversation…
            </div>
          </div>
        ) : (
          <>
            {/* Header */}
            <div style={{
              padding: '0.9rem 1.25rem',
              borderBottom: '1px solid var(--color-border)',
              display: 'flex', alignItems: 'center', gap: '0.75rem',
              background: 'var(--color-surface)',
            }}>
              <div style={{ fontSize: '1.1rem' }}>💬</div>
              <div>
                <div style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--color-text)' }}>
                  Session: {selectedSession.slice(0, 16)}…
                </div>
                <div style={{ fontSize: '0.7rem', color: 'var(--color-text-faint)' }}>
                  {turns.length} messages
                </div>
              </div>
              <div style={{ marginLeft: 'auto', display: 'flex', gap: '0.5rem' }}>
                <button
                  onClick={() => exportSession(selectedSession)}
                  style={{
                    padding: '0.35rem 0.85rem', borderRadius: '8px',
                    border: '1px solid var(--color-border)',
                    background: 'transparent', color: 'var(--color-text-muted)',
                    cursor: 'pointer', fontFamily: 'inherit', fontSize: '0.78rem',
                  }}
                >⬇️ Export</button>
                <button
                  onClick={() => deleteSession(selectedSession)}
                  style={{
                    padding: '0.35rem 0.85rem', borderRadius: '8px',
                    border: '1px solid rgba(239,68,68,0.3)',
                    background: 'rgba(239,68,68,0.08)', color: '#f87171',
                    cursor: 'pointer', fontFamily: 'inherit', fontSize: '0.78rem',
                  }}
                >🗑️ Delete</button>
              </div>
            </div>

            {/* Messages */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '1.25rem' }}>
              {turns.length === 0 ? (
                <div style={{ textAlign: 'center', color: 'var(--color-text-faint)', marginTop: '2rem' }}>
                  No messages in this session.
                </div>
              ) : turns.map((turn, i) => (
                <MessageBubble key={i} turn={turn} />
              ))}
              <div ref={bottomRef} />
            </div>
          </>
        )}
      </div>
    </div>
  );
}

const iconBtnStyle = {
  background: 'none', border: 'none',
  cursor: 'pointer', padding: '3px 5px',
  borderRadius: '6px', fontSize: '0.8rem',
  color: 'var(--color-text-faint)',
  transition: 'background 0.15s',
};
