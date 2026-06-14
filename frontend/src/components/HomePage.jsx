import React, { useState } from 'react';

export default function HomePage({ authUser, onStartChat, onNavigate }) {
  const [showFAQ, setShowFAQ] = useState({});

  const toggleFAQ = (index) => {
    setShowFAQ(prev => ({ ...prev, [index]: !prev[index] }));
  };

  const handleStart = () => {
    if (authUser) {
      if (authUser.role === 'admin') {
        onNavigate('admin');
      } else {
        onNavigate('chat');
      }
    } else {
      // Trigger login prompt or guest option
      onStartChat();
    }
  };

  const faqs = [
    { q: "Is internet required for Rudran Tamil AI?", a: "No! Rudran is designed to run 100% offline using your local CPU memory. No data is sent online, guaranteeing complete privacy." },
    { q: "What languages does the model support?", a: "Rudran natively understands Tamil, English, and Tanglish (e.g. 'enna panra nee' translates script dynamically)." },
    { q: "How do I setup voice activation?", a: "Go to the Downloads page, install the background agent daemon, and complete the 3-sample Voice Security calibration." }
  ];

  return (
    <div style={{ background: 'var(--color-bg)', color: 'var(--color-text)', minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Navbar */}
      <nav style={{ position: 'sticky', top: 0, zIndex: 100, background: 'rgba(10, 10, 20, 0.8)', backdropFilter: 'blur(12px)', borderBottom: '1px solid var(--color-border)' }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '1rem 2rem', display: 'flex', alignItems: 'center', justifyBetween: 'space-between', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', cursor: 'pointer' }} onClick={() => onNavigate('home')}>
            <div style={{ width: '36px', height: '36px', borderRadius: '8px', background: 'linear-gradient(135deg, var(--color-accent), var(--color-teal))', display: 'flex', alignItems: 'center', justifyCenter: 'center', justifyContent: 'center', fontSize: '1.2rem', boxShadow: 'var(--shadow-accent)' }}>🤖</div>
            <span style={{ fontWeight: 800, fontSize: '1.2rem', letterSpacing: '0.02em' }}>ருத்ரன் AI</span>
          </div>
          <div style={{ display: 'flex', gap: '1.5rem', fontSize: '0.85rem', fontWeight: 600 }}>
            <button onClick={() => onNavigate('downloads')} style={{ background: 'none', border: 'none', color: 'var(--color-text-muted)', cursor: 'pointer', fontFamily: 'inherit' }}>Downloads</button>
            <button onClick={() => onNavigate('docs')} style={{ background: 'none', border: 'none', color: 'var(--color-text-muted)', cursor: 'pointer', fontFamily: 'inherit' }}>Docs</button>
            <button onClick={handleStart} style={{ background: 'var(--color-accent)', color: '#ffffff', border: 'none', borderRadius: '999px', padding: '0.4rem 1.25rem', cursor: 'pointer', fontFamily: 'inherit', boxShadow: 'var(--shadow-accent)', transition: 'transform 0.2s' }} onMouseEnter={e => e.target.style.transform = 'scale(1.05)'} onMouseLeave={e => e.target.style.transform = 'none'}>
              Start Chat
            </button>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <header style={{ padding: '6rem 2rem 4rem', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', gap: '1.5rem', position: 'relative' }}>
        <div style={{ position: 'absolute', top: '10%', left: '15%', width: '250px', height: '250px', borderRadius: '50%', background: 'var(--color-accent-glow)', filter: 'blur(80px)', zIndex: 0 }} />
        <div style={{ position: 'absolute', bottom: '10%', right: '15%', width: '250px', height: '250px', borderRadius: '50%', background: 'var(--color-teal-glow)', filter: 'blur(80px)', zIndex: 0 }} />
        
        <div style={{ zIndex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem' }}>
          <div style={{ padding: '0.35rem 1rem', borderRadius: '999px', border: '1px solid var(--color-teal)', color: 'var(--color-teal)', fontSize: '0.75rem', fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase' }}>
            ⚡ Tamil First AI Ecosystem
          </div>
          <h1 style={{ fontSize: '3rem', fontWeight: 900, lineHeight: 1.2, margin: 0, background: 'linear-gradient(135deg, var(--color-text), var(--color-accent-light))', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
            ருத்ரன் தமிழ் AI
          </h1>
          <p style={{ fontSize: '1.25rem', color: 'var(--color-text-muted)', maxWidth: '600px', margin: 0 }}>
            Understands Tamil, English, and Tanglish. Chat, analyze PDFs, run automations - privately on your own computer.
          </p>
          <div style={{ display: 'flex', gap: '1rem', marginTop: '1rem' }}>
            <button onClick={handleStart} style={{ background: 'var(--color-accent)', color: '#ffffff', border: 'none', borderRadius: '10px', padding: '0.75rem 1.75rem', fontSize: '0.95rem', fontWeight: 700, cursor: 'pointer', boxShadow: 'var(--shadow-accent)' }}>
              💬 Start Chatting
            </button>
            <button onClick={() => onNavigate('downloads')} style={{ background: 'var(--color-surface-2)', color: 'var(--color-text)', border: '1px solid var(--color-border)', borderRadius: '10px', padding: '0.75rem 1.75rem', fontSize: '0.95rem', fontWeight: 600, cursor: 'pointer' }}>
              ⬇️ Download Desktop App
            </button>
          </div>
        </div>
      </header>

      {/* Features Grid */}
      <section style={{ maxWidth: '1200px', margin: '0 auto', padding: '4rem 2rem', width: '100%' }}>
        <h2 style={{ fontSize: '2rem', fontWeight: 800, textAlign: 'center', marginBottom: '2.5rem' }}>
          Explore Platform Capabilities
        </h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.25rem' }}>
          {[
            { icon: '🗣️', t: 'Tamil Intelligence', d: 'Normlize Tanglish text to Tamil scripts automatically in real-time.' },
            { icon: '🔒', t: 'Voice Biometrics', d: 'Dynamic voice enroll checks verification digits before sensitive system tasks.' },
            { icon: '📚', t: 'RAG Knowledge base', d: 'Upload document PDFs or TXTs and perform search queries locally.' },
            { icon: '🧠', t: 'Memory Engine', d: 'Auto-extract fact records, preferences, and categories across user chats.' },
            { icon: '⚙️', t: 'Command Automation', d: 'Enqueue custom executable tasks for agent-registered devices.' },
            { icon: '🎯', t: 'Skills Marketplace', d: 'Create custom agent skill presets containing custom prompts and overrides.' },
            { icon: '🔌', t: 'Plugin System', d: 'Dynamic upload of Python plugin classes with AST sandbox parsing.' },
            { icon: '📝', t: 'VS Code Extension', d: 'Sidebar chat panel directly tracking active workspace code focuses.' }
          ].map((feat, i) => (
            <div key={i} className="card" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: '16px', padding: '1.5rem', transition: 'all 0.2s' }}>
              <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>{feat.icon}</div>
              <h4 style={{ fontWeight: 700, fontSize: '1.05rem', margin: 0, color: 'var(--color-text)' }}>{feat.t}</h4>
              <p style={{ fontSize: '0.82rem', color: 'var(--color-text-muted)', marginTop: '0.5rem', lineHeight: 1.5 }}>{feat.d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How It Works */}
      <section style={{ background: 'var(--color-surface-2)', borderY: '1px solid var(--color-border)', padding: '4rem 2rem' }}>
        <div style={{ maxWidth: '900px', margin: '0 auto', textAlign: 'center' }}>
          <h2 style={{ fontSize: '2rem', fontWeight: 800, marginBottom: '2.5rem' }}>How It Works</h2>
          <div style={{ display: 'flex', flexDirection: 'column', smDirection: 'row', gap: '2rem', justifyContent: 'center', flexWrap: 'wrap' }}>
            {[
              { num: '01', title: 'Open Interface', desc: 'Log in securely or proceed directly with Guest Mode access.' },
              { num: '02', title: 'Interact', desc: 'Type queries in Tamil/Tanglish or record microphone commands.' },
              { num: '03', title: 'Response Output', desc: 'Dynamic router selects best model (TinyLlama/Mistral) for instant output.' }
            ].map((step, i) => (
              <div key={i} style={{ flex: 1, minWidth: '220px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.5rem' }}>
                <div style={{ fontSize: '2.2rem', fontWeight: 900, color: 'var(--color-accent-light)' }}>{step.num}</div>
                <h4 style={{ fontWeight: 700, fontSize: '1.05rem', margin: 0, color: 'var(--color-text)' }}>{step.title}</h4>
                <p style={{ fontSize: '0.82rem', color: 'var(--color-text-muted)', lineHeight: 1.5, margin: 0 }}>{step.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ & Support */}
      <section style={{ maxWidth: '800px', margin: '0 auto', padding: '4rem 2rem', width: '100%' }}>
        <h2 style={{ fontSize: '2rem', fontWeight: 800, textAlign: 'center', marginBottom: '2rem' }}>Frequently Asked Questions</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {faqs.map((faq, i) => (
            <div key={i} style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: '10px', overflow: 'hidden' }}>
              <button onClick={() => toggleFAQ(i)} style={{ width: '100%', padding: '1rem', background: 'none', border: 'none', textAlign: 'left', fontWeight: 700, color: 'var(--color-text)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer', fontFamily: 'inherit' }}>
                <span>{faq.q}</span>
                <span>{showFAQ[i] ? '▲' : '▼'}</span>
              </button>
              {showFAQ[i] && (
                <div style={{ padding: '1rem', borderTop: '1px solid var(--color-border)', fontSize: '0.85rem', color: 'var(--color-text-muted)', lineHeight: 1.6 }}>
                  {faq.a}
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer style={{ marginTop: 'auto', borderTop: '1px solid var(--color-border)', background: 'var(--color-surface)', padding: '2rem 1rem', textAlign: 'center', fontSize: '0.8rem', color: 'var(--color-text-faint)' }}>
        © 2026 Rudran Tamil AI. Built with ❤️ for Tamil users. 100% Free & Open Source.
      </footer>
    </div>
  );
}
