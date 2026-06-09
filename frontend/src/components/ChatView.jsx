import React, { useState, useRef, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import { runAgent, normalizeTamil, transcribeAudio, generateSpeech } from '../services/api';
import { useRuntime } from '../App';
import { CloudBanner } from './RuntimeWidget';

const SUGGESTIONS = [
  '🙏 vanakkam! enna panra nee?',
  'Analyze this PDF, summarize + translate to Tamil',
  'Calculate: (25 * 48) + (100 / 4)',
  'Translate: "Good morning, have a great day" to Tamil',
  'What is machine learning? Explain simply.',
  'தமிழ் மொழியின் வரலாறு என்ன?',
];

function TypingIndicator() {
  return (
    <div className="message assistant">
      <div className="message-avatar">🤖</div>
      <div className="message-body">
        <div className="message-bubble" style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)' }}>
          <div className="typing-bubble">
            <div className="typing-dot" /><div className="typing-dot" /><div className="typing-dot" />
          </div>
        </div>
      </div>
    </div>
  );
}

function AgentStepsPanel({ steps }) {
  const [open, setOpen] = useState(false);
  if (!steps || steps.length === 0) return null;
  return (
    <div style={{
      marginTop: '0.5rem',
      border: '1px solid rgba(124,92,252,0.2)',
      borderRadius: 'var(--radius-md)',
      overflow: 'hidden',
      fontSize: '0.78rem',
    }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', textAlign: 'left',
          padding: '0.4rem 0.75rem',
          background: 'rgba(124,92,252,0.1)',
          border: 'none', cursor: 'pointer',
          color: 'var(--color-accent-light)',
          fontFamily: 'inherit', fontSize: '0.75rem',
        }}
      >
        {open ? '▲' : '▼'} Agent: {steps.length} steps executed
      </button>
      {open && (
        <div style={{ padding: '0.5rem 0.75rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
          {steps.map(s => (
            <div key={s.step_id} style={{
              display: 'flex', gap: '0.5rem', alignItems: 'flex-start',
              padding: '0.3rem 0.5rem',
              background: s.error ? 'rgba(239,68,68,0.1)' : 'rgba(255,255,255,0.03)',
              borderRadius: '6px',
            }}>
              <span style={{ color: 'var(--color-accent-light)', fontWeight: 600 }}>
                {s.step_id}.
              </span>
              <span style={{ color: 'var(--color-teal)', textTransform: 'capitalize' }}>{s.action}</span>
              <span style={{ color: 'var(--color-text-faint)', marginLeft: 'auto' }}>
                {s.duration_ms?.toFixed(0)}ms
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function TanglishBadge({ original, normalized }) {
  if (!normalized || original === normalized) return null;
  return (
    <div style={{
      fontSize: '0.7rem', padding: '0.2rem 0.6rem',
      background: 'rgba(13,211,197,0.08)',
      border: '1px solid rgba(13,211,197,0.2)',
      borderRadius: 'var(--radius-sm)',
      color: 'var(--color-teal)', marginBottom: '0.3rem',
    }}>
      🔄 Tanglish → Tamil: <em>{normalized}</em>
    </div>
  );
}

export default function ChatView({ sessionId }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [agentMode, setAgentMode] = useState(false);
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);

  // Phase 4: Runtime context
  const { runtime, selectedModel } = useRuntime();

  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handlePlayTTS = async (text, lang) => {
    try {
      // Strip markdown for cleaner speech synthesis
      const cleanText = text.replace(/[*#`_\-]/g, '').trim();
      if (!cleanText) return;
      const blob = await generateSpeech(cleanText, lang === 'ta' ? 'ta' : 'en');
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.play();
    } catch (err) {
      console.error("TTS playback failed:", err);
      alert("TTS playback failed: " + err.message);
    }
  };

  const startRecording = async () => {
    audioChunksRef.current = [];
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' });
        stream.getTracks().forEach(track => track.stop());
        
        setTranscribing(true);
        try {
          const res = await transcribeAudio(audioBlob);
          if (res.text) {
            setInput(res.text);
          }
        } catch (err) {
          console.error("Transcription failed:", err);
          alert("Transcription failed: " + err.message);
        } finally {
          setTranscribing(false);
        }
      };

      mediaRecorder.start();
      setRecording(true);
    } catch (err) {
      console.error("Mic access denied:", err);
      alert("Microphone access denied: " + err.message);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && recording) {
      mediaRecorderRef.current.stop();
      setRecording(false);
    }
  };

  const toggleRecording = () => {
    if (recording) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  const handleSend = useCallback(async (text) => {
    const msg = (text || input).trim();
    if (!msg || loading) return;

    setMessages(prev => [...prev, { role: 'user', content: msg, id: Date.now() }]);
    setInput('');
    setLoading(true);

    // Resolve model override (auto → let backend decide, else pass explicit model)
    const modelOverride = selectedModel && selectedModel !== 'auto' ? selectedModel : undefined;

    try {
      if (agentMode) {
        const data = await runAgent(msg, sessionId, true);
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: data.final_response,
          intent: 'agent',
          source: `agent (${data.step_count} steps)`,
          duration_ms: data.total_duration_ms,
          agent_steps: data.steps,
          id: Date.now(),
        }]);
      } else {
        // SSE real-time token streaming via POST /api/chat/stream
        const streamBody = { message: msg, session_id: sessionId };
        if (modelOverride) streamBody.model = modelOverride;

        const response = await fetch('http://localhost:8000/api/chat/stream', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(streamBody),
        });
        
        if (!response.ok) {
          const err = await response.json().catch(() => ({ detail: response.statusText }));
          throw new Error(err.detail || `HTTP ${response.status}`);
        }
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let done = false;
        let assistantMsgId = Date.now();
        
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: '',
          id: assistantMsgId,
          streaming: true
        }]);
        
        let accumulatedText = '';
        let buffer = '';
        
        while (!done) {
          const { value, done: readerDone } = await reader.read();
          done = readerDone;
          if (value) {
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop();
            
            for (const line of lines) {
              const cleaned = line.trim();
              if (cleaned.startsWith('data:')) {
                try {
                  const data = JSON.parse(cleaned.substring(5).trim());
                  if (data.type === 'meta') {
                    setMessages(prev => prev.map(m => 
                      m.id === assistantMsgId
                        ? { 
                            ...m, 
                            intent: data.intent,
                            language: data.lang,
                            model_used: data.model,
                            tanglish_converted: data.tanglish,
                            normalized_input: data.normalized
                          }
                        : m
                    ));
                  } else if (data.type === 'token') {
                    if (data.error) {
                      accumulatedText += `\n⚠️ ${data.error}`;
                      setMessages(prev => prev.map(m => 
                        m.id === assistantMsgId ? { ...m, content: accumulatedText, error: true } : m
                      ));
                    } else if (data.done) {
                      setMessages(prev => prev.map(m => 
                        m.id === assistantMsgId ? { ...m, streaming: false } : m
                      ));
                    } else if (data.token) {
                      accumulatedText += data.token;
                      setMessages(prev => prev.map(m => 
                        m.id === assistantMsgId ? { ...m, content: accumulatedText } : m
                      ));
                    }
                  }
                } catch (e) {
                  console.error("Error parsing streaming chunk:", e);
                }
              }
            }
          }
        }
      }
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `⚠️ ${err.message}`,
        id: Date.now(), error: true,
      }]);
    } finally {
      setLoading(false);
    }
  }, [input, loading, sessionId, agentMode, selectedModel]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  return (
    <div className="chat-view">
      {/* Phase 4: Cloud banner when running on cloud AI */}
      <CloudBanner visible={runtime?.runtime === 'cloud'} />
      <div className="messages-container">
        {messages.length === 0 ? (
          <div className="welcome-screen">
            <div className="welcome-icon">🤖</div>
            <div>
              <h2>Tamil AI Assistant v4</h2>
              <p style={{ marginTop: '0.5rem' }}>
                Supports <strong>Tamil</strong> · <strong>English</strong> · <strong>Tanglish</strong><br/>
                Multi-step Agent · Smart Model Routing · RAG Knowledge Base · Voice AI<br/>
                <span style={{ color: 'var(--color-accent-light)', fontSize: '0.8rem' }}>
                  {runtime?.runtime === 'cloud' ? '🔵 Cloud AI Active' :
                   runtime?.runtime === 'local' ? '🟢 Local AI Active' :
                   runtime?.runtime === 'hybrid' ? '🟣 Hybrid Mode Active' : '⏳ Detecting AI…'}
                </span>
              </p>
            </div>
            <div className="suggestion-chips">
              {SUGGESTIONS.map((s, i) => (
                <button key={i} className="chip" onClick={() => handleSend(s)}>{s}</button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {messages.map(msg => (
              <div key={msg.id} className={`message ${msg.role}`}>
                <div className="message-avatar">
                  {msg.role === 'user' ? '👤' : '🤖'}
                </div>
                <div className="message-body">
                  {msg.tanglish_converted && (
                    <TanglishBadge original={msg.content} normalized={msg.normalized_input} />
                  )}
                  <div className="message-bubble-wrapper" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <div className="message-bubble">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                    {msg.role === 'assistant' && !msg.error && msg.content && (
                      <button 
                        onClick={() => handlePlayTTS(msg.content, msg.language || 'ta')}
                        className="tts-play-btn"
                        style={{
                          background: 'transparent',
                          border: 'none',
                          cursor: 'pointer',
                          color: 'var(--color-text-faint)',
                          fontSize: '1.1rem',
                          padding: '4px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          transition: 'color 0.2s',
                          flexShrink: 0
                        }}
                        title="Speak response"
                      >
                        🔊
                      </button>
                    )}
                  </div>
                  {msg.role === 'assistant' && !msg.error && (
                    <>
                      <div className="message-meta">
                        {msg.intent && <span className="intent-tag">{msg.intent}</span>}
                        {msg.language && <span className="lang-tag">{msg.language}</span>}
                        {msg.model_used && (
                          <span style={{
                            padding: '1px 8px', borderRadius: 'var(--radius-full)',
                            background: 'rgba(245,158,11,0.15)',
                            border: '1px solid rgba(245,158,11,0.3)',
                            color: 'var(--color-warning)', fontSize: '0.65rem',
                          }}>
                            🤖 {msg.model_used}
                          </span>
                        )}
                        {msg.source && <span style={{ color: 'var(--color-text-faint)' }}>via {msg.source}</span>}
                        {msg.duration_ms && (
                          <span style={{ color: 'var(--color-text-faint)' }}>
                            {msg.duration_ms.toFixed(0)}ms
                          </span>
                        )}
                      </div>
                      <AgentStepsPanel steps={msg.agent_steps} />
                    </>
                  )}
                </div>
              </div>
            ))}
            {loading && !messages[messages.length - 1]?.streaming && <TypingIndicator />}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="input-area">
        {/* Agent mode toggle */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: '0.75rem',
          marginBottom: '0.5rem', padding: '0 0.25rem',
        }}>
          <button
            onClick={() => setAgentMode(a => !a)}
            style={{
              display: 'flex', alignItems: 'center', gap: '0.4rem',
              padding: '0.25rem 0.75rem',
              borderRadius: 'var(--radius-full)',
              border: agentMode
                ? '1px solid rgba(124,92,252,0.6)'
                : '1px solid var(--color-border)',
              background: agentMode ? 'rgba(124,92,252,0.2)' : 'transparent',
              color: agentMode ? 'var(--color-accent-light)' : 'var(--color-text-faint)',
              cursor: 'pointer', fontSize: '0.75rem', fontFamily: 'inherit',
              transition: 'all 0.2s ease',
            }}
            id="agent-mode-toggle"
          >
            🤖 {agentMode ? 'Agent Mode ON' : 'Agent Mode'}
          </button>
          {agentMode && (
            <span style={{ fontSize: '0.7rem', color: 'var(--color-accent-light)' }}>
              Multi-step reasoning enabled
            </span>
          )}
        </div>

        <div className="input-wrapper">
          <textarea
            className="chat-input"
            id="chat-input"
            placeholder={agentMode
              ? "Ask a complex question (agent will plan + execute multiple steps)…"
              : "Type in Tamil, English, or Tanglish… (Enter to send)"
            }
            value={input}
            onChange={(e) => {
              setInput(e.target.value);
              e.target.style.height = 'auto';
              e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
            }}
            onKeyDown={handleKeyDown}
            disabled={loading}
            rows={1}
          />
          <button
            className={`mic-btn ${recording ? 'recording' : ''}`}
            onClick={toggleRecording}
            disabled={loading || transcribing}
            style={{
              background: recording ? 'rgba(239,68,68,0.2)' : 'transparent',
              border: recording ? '1px solid rgba(239,68,68,0.4)' : 'none',
              borderRadius: '50%',
              cursor: 'pointer',
              color: recording ? 'var(--color-error)' : 'var(--color-text-faint)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '8px',
              width: '36px',
              height: '36px',
              transition: 'all 0.3s ease',
              flexShrink: 0,
            }}
            title={recording ? "Stop recording" : "Record voice input"}
          >
            {transcribing ? (
              <div className="typing-dot" style={{ width: '4px', height: '4px', background: 'var(--color-text-faint)', margin: 0 }} />
            ) : recording ? (
              "🔴"
            ) : (
              "🎙️"
            )}
          </button>
          <button
            className="send-btn" id="send-btn"
            onClick={() => handleSend()}
            disabled={loading || !input.trim() || transcribing}
          >
            {loading && !messages[messages.length - 1]?.streaming ? (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" strokeDasharray="40" strokeDashoffset="10">
                  <animateTransform attributeName="transform" type="rotate" dur="0.8s" from="0 12 12" to="360 12 12" repeatCount="indefinite" />
                </circle>
              </svg>
            ) : (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            )}
          </button>
        </div>
        <p className="input-hint">
          Tanglish auto-detected ✦ Real-time streaming ✦ Context memory
          {selectedModel && selectedModel !== 'auto' && (
            <> ✦ Model: <strong>{selectedModel}</strong></>
          )}
        </p>
      </div>
    </div>
  );
}
