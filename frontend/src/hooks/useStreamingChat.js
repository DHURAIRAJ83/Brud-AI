/**
 * Streaming Chat Hook — useStreamingChat
 * Connects to /api/chat/stream via EventSource.
 * Tokens appear word-by-word in real-time.
 */
import { useState, useRef, useCallback } from 'react';

const BASE = 'http://localhost:8000';

export function useStreamingChat(sessionId) {
  const [messages, setMessages]   = useState([]);
  const [streaming, setStreaming] = useState(false);
  const [meta, setMeta]           = useState(null);
  const esRef                     = useRef(null);

  const sendStream = useCallback(async (userText) => {
    if (streaming || !userText.trim()) return;

    // Add user message
    const userId = Date.now();
    setMessages(prev => [...prev, { id: userId, role: 'user', content: userText }]);

    // Placeholder assistant message
    const assistId = userId + 1;
    setMessages(prev => [...prev, {
      id: assistId, role: 'assistant', content: '', streaming: true,
    }]);

    setStreaming(true);
    setMeta(null);

    // Close any existing stream
    if (esRef.current) { esRef.current.close(); }

    const url = `${BASE}/api/chat/stream?message=${encodeURIComponent(userText)}&session_id=${sessionId}`;
    const es = new EventSource(url);
    esRef.current = es;

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === 'meta') {
          setMeta(data);
          return;
        }

        if (data.error) {
          setMessages(prev => prev.map(m =>
            m.id === assistId ? { ...m, content: `⚠️ ${data.error}`, streaming: false } : m
          ));
          setStreaming(false);
          es.close();
          return;
        }

        if (data.done) {
          setMessages(prev => prev.map(m =>
            m.id === assistId ? { ...m, streaming: false } : m
          ));
          setStreaming(false);
          es.close();
          return;
        }

        // Append token
        if (data.token) {
          setMessages(prev => prev.map(m =>
            m.id === assistId
              ? { ...m, content: m.content + data.token }
              : m
          ));
        }
      } catch (e) {
        console.error('SSE parse error:', e);
      }
    };

    es.onerror = () => {
      setMessages(prev => prev.map(m =>
        m.id === assistId
          ? { ...m, content: m.content || '⚠️ Stream connection failed.', streaming: false }
          : m
      ));
      setStreaming(false);
      es.close();
    };
  }, [streaming, sessionId]);

  const stopStream = useCallback(() => {
    if (esRef.current) { esRef.current.close(); }
    setStreaming(false);
    setMessages(prev => prev.map(m =>
      m.streaming ? { ...m, streaming: false, content: m.content + ' [stopped]' } : m
    ));
  }, []);

  const clearMessages = useCallback(() => setMessages([]), []);

  return { messages, streaming, meta, sendStream, stopStream, clearMessages };
}
