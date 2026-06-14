import React from 'react';

export default function DownloadsPage() {
  const versions = {
    agent: 'v5.0.0-beta',
    extension: 'v1.2.0',
    desktop: 'v4.1.0'
  };

  return (
    <div style={{ padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1.5rem', overflowY: 'auto', height: '100%' }}>
      <div>
        <h2 style={{ fontSize: '1.6rem', fontWeight: 800, background: 'linear-gradient(135deg, var(--color-accent-light), var(--color-teal))', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          ⬇️ Desktop Agent Downloads & Setup
        </h2>
        <p style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem', marginTop: '0.2rem' }}>
          Install the native Electron desktop wrappers, CLI agent daemons, or VS Code Workspace extension helper.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.25rem' }}>
        {/* Windows Download */}
        <div className="card" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: '16px', padding: '1.5rem', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>🪟</div>
            <h4 style={{ fontWeight: 700, fontSize: '1.05rem', margin: 0, color: 'var(--color-text)' }}>Windows Electron App</h4>
            <p style={{ fontSize: '0.82rem', color: 'var(--color-text-muted)', marginTop: '0.5rem', lineHeight: 1.5 }}>
              Native executable bundle containing the background agent daemon, system tray operations, and dynamic UI panels.
            </p>
            <div style={{ fontSize: '0.72rem', color: 'var(--color-text-faint)', marginTop: '0.5rem', fontWeight: 600 }}>
              Version: {versions.desktop} · Windows 10/11 x64
            </div>
          </div>
          <button className="btn btn-primary" style={{ marginTop: '1.5rem', width: '100%' }} onClick={() => alert('Download starting for Windows installer (Rudran_Tamil_AI_x64.exe)...')}>
            ⬇️ Download for Windows
          </button>
        </div>

        {/* Linux Download */}
        <div className="card" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: '16px', padding: '1.5rem', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>🐧</div>
            <h4 style={{ fontWeight: 700, fontSize: '1.05rem', margin: 0, color: 'var(--color-text)' }}>Linux Debian AppImage</h4>
            <p style={{ fontSize: '0.82rem', color: 'var(--color-text-muted)', marginTop: '0.5rem', lineHeight: 1.5 }}>
              Self-contained binary executable package designed for Ubuntu, Debian, Arch Linux, and Fedora systems.
            </p>
            <div style={{ fontSize: '0.72rem', color: 'var(--color-text-faint)', marginTop: '0.5rem', fontWeight: 600 }}>
              Version: {versions.desktop} · Linux x64
            </div>
          </div>
          <button className="btn btn-ghost" style={{ marginTop: '1.5rem', width: '100%' }} onClick={() => alert('Download starting for Linux binary (Rudran_Tamil_AI.AppImage)...')}>
            ⬇️ Download AppImage
          </button>
        </div>

        {/* VS Code Extension */}
        <div className="card" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: '16px', padding: '1.5rem', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>📝</div>
            <h4 style={{ fontWeight: 700, fontSize: '1.05rem', margin: 0, color: 'var(--color-text)' }}>VS Code Extension</h4>
            <p style={{ fontSize: '0.82rem', color: 'var(--color-text-muted)', marginTop: '0.5rem', lineHeight: 1.5 }}>
              Open-source editor sidebar panel. Scan repository symbol indexes, execute tests, and ask queries directly from VS Code.
            </p>
            <div style={{ fontSize: '0.72rem', color: 'var(--color-text-faint)', marginTop: '0.5rem', fontWeight: 600 }}>
              Version: {versions.extension} · VS Code Marketplace
            </div>
          </div>
          <button className="btn btn-ghost" style={{ marginTop: '1.5rem', width: '100%' }} onClick={() => alert('Opening VS Code Marketplace (Rudran Tamil AI Extension)...')}>
            🔌 Install Extension
          </button>
        </div>
      </div>

      {/* Ollama Local Guide */}
      <div className="card" style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderRadius: '18px', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <h3 style={{ fontSize: '1.2rem', fontWeight: 800, margin: 0, color: 'var(--color-text)' }}>🚀 Local AI Setup: Ollama Guide</h3>
        <p style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)', lineHeight: 1.6, margin: 0 }}>
          Rudran Tamil AI features a **Hybrid Runtime** that defaults to your local computer's processor before falling back to cloud services. Follow these instructions to run fully offline:
        </p>
        
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem', marginTop: '0.5rem' }}>
          <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: '10px', padding: '1rem' }}>
            <div style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--color-accent-light)' }}>Step 1: Download Ollama</div>
            <p style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', marginTop: '0.25rem', lineHeight: 1.5 }}>
              Go to <a href="https://ollama.com" target="_blank" rel="noreferrer" style={{ color: 'var(--color-teal)', textDecoration: 'underline' }}>ollama.com</a> and download the installer for Windows, macOS, or Linux. Run the install setup wizard.
            </p>
          </div>
          <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: '10px', padding: '1rem' }}>
            <div style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--color-accent-light)' }}>Step 2: Pull Default LLM</div>
            <p style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', marginTop: '0.25rem', lineHeight: 1.5 }}>
              Open terminal or Command Prompt and download Mistral/TinyLlama:
              <code style={{ display: 'block', background: 'var(--color-surface-2)', padding: '0.25rem 0.5rem', borderRadius: '4px', marginTop: '0.25rem', fontSize: '0.72rem', fontFamily: 'var(--font-mono)' }}>ollama pull mistral</code>
            </p>
          </div>
          <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: '10px', padding: '1rem' }}>
            <div style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--color-accent-light)' }}>Step 3: Connect Tray</div>
            <p style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', marginTop: '0.25rem', lineHeight: 1.5 }}>
              Launch your Rudran application. It will detect the local endpoint at <code style={{ fontSize: '0.72rem', fontFamily: 'var(--font-mono)' }}>localhost:11434</code> automatically and route queries locally.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
