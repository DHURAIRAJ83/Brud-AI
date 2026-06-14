import React, { useState } from 'react';

const DOC_SECTIONS = [
  {
    id: 'getting-started',
    title: '🚀 Getting Started',
    content: (
      <div>
        <p>Rudran Tamil AI is a hybrid Local-first AI ecosystem built specifically for Tamil users. It processes commands, summarizes text, and translates languages natively on your computer with complete privacy control.</p>
        <h4 style={{ color: 'var(--color-accent-light)', marginTop: '1rem', fontSize: '0.95rem' }}>Minimum System Specifications</h4>
        <ul style={{ paddingLeft: '1.25rem', marginTop: '0.25rem', fontSize: '0.82rem', lineHeight: 1.6 }}>
          <li>**Operating System**: Windows 10/11 x64, macOS 11+, Linux Ubuntu 20.04+</li>
          <li>**RAM**: 8 GB minimum (16 GB recommended for full local model processing)</li>
          <li>**Storage**: 10 GB available HDD/SSD space</li>
          <li>**GPU**: Optional (CPU processing is fully optimized with smart routing)</li>
        </ul>
      </div>
    )
  },
  {
    id: 'voice-setup',
    title: '🗣️ Voice Biometrics Setup',
    content: (
      <div>
        <p>Rudran features a voice-activated safety shield that validates who is speaking before executing high-risk commands (e.g. deleting files, running console terminal scripts).</p>
        <h4 style={{ color: 'var(--color-accent-light)', marginTop: '1rem', fontSize: '0.95rem' }}>Steps to Enroll Your Voice Profile:</h4>
        <ol style={{ paddingLeft: '1.25rem', marginTop: '0.25rem', fontSize: '0.82rem', lineHeight: 1.6 }}>
          <li>Navigate to the **Voice Security** tab inside your application menu.</li>
          <li>Enter a unique identifier name for your microphone setup (e.g. "Home Mic").</li>
          <li>Record three distinct speech samples (speaking the wake word sequence "Hey Rudran" or "ருத்ரன்").</li>
          <li>Submit the enrollment. Our backend extracts MFCC features and generates a signed biometric signature vector.</li>
        </ol>
      </div>
    )
  },
  {
    id: 'rag-setup',
    title: '📚 RAG Knowledge Base',
    content: (
      <div>
        <p>Retrieve context instantly from uploaded documents with the Retrieval-Augmented Generation (RAG) module. Ask questions in Tamil or Tanglish and obtain references directly from PDFs or plain text documents.</p>
        <h4 style={{ color: 'var(--color-accent-light)', marginTop: '1rem', fontSize: '0.95rem' }}>Supported Formats:</h4>
        <ul style={{ paddingLeft: '1.25rem', marginTop: '0.25rem', fontSize: '0.82rem', lineHeight: 1.6 }}>
          <li>**Documents**: Portable Document Format (`.pdf`), Microsoft Word (`.docx`), plain text (`.txt`).</li>
          <li>**Size Limit**: Maximum file size is 20 megabytes (MB) per upload.</li>
          <li>**Ingestion**: Files are automatically parsed, vectorized using sentence transformers, and saved to your local FAISS vector store database index.</li>
        </ul>
      </div>
    )
  },
  {
    id: 'plugin-dev',
    title: '🔌 Custom Plugin Development',
    content: (
      <div>
        <p>Extend the AI model functionality with custom tools. Plugins are written in plain Python and executed inside a strict AST-validated sandboxed runtime framework.</p>
        <h4 style={{ color: 'var(--color-accent-light)', marginTop: '1rem', fontSize: '0.95rem' }}>Basic Plugin Template Structure:</h4>
        <pre style={{ background: 'var(--color-surface-2)', padding: '0.75rem', borderRadius: '8px', border: '1px solid var(--color-border)', fontFamily: 'var(--font-mono)', fontSize: '0.75rem', overflowX: 'auto', marginTop: '0.5rem' }}>
{`# custom_weather.py
PLUGIN_NAME = "weather_finder"
PLUGIN_DESCRIPTION = "Retrieve live weather report parameters"
PLUGIN_INTENTS = ["get_weather", "weather_status"]

async def execute(message: str, **kwargs) -> str:
    # message contains the natural language input prompt
    # Perform calculations, API requests, or string formatting
    return "The current temperature in Chennai is 32°C with light rain."
`}
        </pre>
      </div>
    )
  }
];

export default function DocsPage() {
  const [activeId, setActiveId] = useState('getting-started');

  const activeDoc = DOC_SECTIONS.find(d => d.id === activeId) || DOC_SECTIONS[0];

  return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* Doc Sidebar */}
      <aside style={{ width: '240px', borderRight: '1px solid var(--color-border)', background: 'var(--color-surface)', display: 'flex', flexDirection: 'column', padding: '1.5rem 1rem', gap: '0.5rem', flexShrink: 0 }}>
        <h3 style={{ fontSize: '0.75rem', color: 'var(--color-text-faint)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 700, paddingLeft: '0.5rem', marginBottom: '0.5rem' }}>
          Documentation Hub
        </h3>
        {DOC_SECTIONS.map(doc => (
          <button
            key={doc.id}
            onClick={() => setActiveId(doc.id)}
            style={{
              width: '100%', textAlign: 'left',
              padding: '0.5rem 0.75rem',
              borderRadius: '8px', border: 'none',
              background: activeId === doc.id ? 'var(--color-surface-2)' : 'transparent',
              color: activeId === doc.id ? 'var(--color-accent-light)' : 'var(--color-text-muted)',
              fontWeight: activeId === doc.id ? 600 : 500,
              cursor: 'pointer', fontFamily: 'inherit', fontSize: '0.82rem',
              transition: 'all 0.15s'
            }}
          >
            {doc.title}
          </button>
        ))}
      </aside>

      {/* Doc Body */}
      <main style={{ flex: 1, padding: '2.5rem', overflowY: 'auto', background: 'var(--color-bg)' }}>
        <h2 style={{ fontSize: '1.6rem', fontWeight: 800, color: 'var(--color-text)', borderBottom: '1px solid var(--color-border)', paddingBottom: '0.5rem' }}>
          {activeDoc.title.substring(3)}
        </h2>
        <div style={{ fontSize: '0.9rem', color: 'var(--color-text-muted)', lineHeight: 1.7, marginTop: '1.25rem' }}>
          {activeDoc.content}
        </div>
      </main>
    </div>
  );
}
