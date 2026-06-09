/**
 * Phase 4: Onboarding Modal
 * Shown when local Ollama is not detected on first load.
 *
 * Flow:
 *   "Local AI Not Found"
 *   → [Install Local AI]  → opens https://ollama.com/download
 *   → [Use Online AI]     → Consent dialog
 *                         → [Accept] → save localStorage, close modal
 *                         → [Cancel] → stay on install option
 */

import React, { useState } from 'react';

export default function OnboardingModal({ onClose, onCloudConsent }) {
  const [step, setStep] = useState('main'); // 'main' | 'consent'

  const handleInstall = () => {
    window.open('https://ollama.com/download', '_blank', 'noopener,noreferrer');
  };

  const handleConsent = () => {
    localStorage.setItem('ai_mode', 'cloud');
    localStorage.setItem('cloud_consent', 'true');
    onCloudConsent?.();
    onClose?.();
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9000,
      background: 'rgba(0,0,0,0.75)',
      backdropFilter: 'blur(8px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      animation: 'fadeIn 0.25s ease',
      padding: '1rem',
    }}>
      <div style={{
        background: 'linear-gradient(135deg, #0f0f1a 0%, #12121e 100%)',
        border: '1px solid rgba(124,92,252,0.25)',
        borderRadius: 20,
        padding: '2.5rem',
        maxWidth: 460,
        width: '100%',
        boxShadow: '0 24px 64px rgba(0,0,0,0.6), 0 0 0 1px rgba(124,92,252,0.1)',
        animation: 'scaleIn 0.2s ease',
      }}>

        {step === 'main' && (
          <>
            {/* Icon */}
            <div style={{
              width: 72, height: 72, borderRadius: '50%',
              background: 'rgba(239,68,68,0.1)',
              border: '2px solid rgba(239,68,68,0.25)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '2rem', marginBottom: '1.5rem',
              margin: '0 auto 1.5rem',
            }}>
              🔌
            </div>

            {/* Title */}
            <h2 style={{
              textAlign: 'center', fontSize: '1.35rem', fontWeight: 800,
              color: '#fff', marginBottom: '0.75rem',
            }}>
              Local AI Not Found
            </h2>

            <p style={{
              textAlign: 'center', color: 'rgba(255,255,255,0.55)',
              fontSize: '0.875rem', lineHeight: 1.6, marginBottom: '2rem',
            }}>
              Ollama is not installed on this computer.<br />
              You can install it for <strong style={{ color: '#22d3a5' }}>free private AI</strong>, or
              continue with our <strong style={{ color: '#60a5fa' }}>secure online AI</strong>.
            </p>

            {/* Options */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {/* Install option */}
              <button
                id="onboarding-install-btn"
                onClick={handleInstall}
                style={{
                  padding: '0.9rem 1.5rem',
                  borderRadius: 12,
                  background: 'linear-gradient(135deg, #22d3a5 0%, #0ea5e9 100%)',
                  border: 'none',
                  color: '#fff',
                  fontSize: '0.9rem',
                  fontWeight: 700,
                  cursor: 'pointer',
                  fontFamily: 'inherit',
                  transition: 'all 0.2s ease',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem',
                }}
                onMouseEnter={e => e.target.style.transform = 'translateY(-1px)'}
                onMouseLeave={e => e.target.style.transform = 'translateY(0)'}
              >
                🖥️ Install Local AI (Free, Private)
              </button>

              {/* Cloud option */}
              <button
                id="onboarding-cloud-btn"
                onClick={() => setStep('consent')}
                style={{
                  padding: '0.9rem 1.5rem',
                  borderRadius: 12,
                  background: 'rgba(96,165,250,0.1)',
                  border: '1px solid rgba(96,165,250,0.3)',
                  color: '#93c5fd',
                  fontSize: '0.9rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  fontFamily: 'inherit',
                  transition: 'all 0.2s ease',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem',
                }}
                onMouseEnter={e => { e.currentTarget.style.background = 'rgba(96,165,250,0.18)'; }}
                onMouseLeave={e => { e.currentTarget.style.background = 'rgba(96,165,250,0.1)'; }}
              >
                ☁️ Use Online AI
              </button>
            </div>

            {/* Footer note */}
            <p style={{
              textAlign: 'center', fontSize: '0.7rem', color: 'rgba(255,255,255,0.25)',
              marginTop: '1.25rem',
            }}>
              You can change this later in the Admin → Runtime panel.
            </p>
          </>
        )}

        {step === 'consent' && (
          <>
            {/* Icon */}
            <div style={{
              width: 72, height: 72, borderRadius: '50%',
              background: 'rgba(96,165,250,0.1)',
              border: '2px solid rgba(96,165,250,0.25)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '2rem', margin: '0 auto 1.5rem',
            }}>
              🔒
            </div>

            <h2 style={{
              textAlign: 'center', fontSize: '1.2rem', fontWeight: 800,
              color: '#fff', marginBottom: '0.75rem',
            }}>
              Privacy Consent
            </h2>

            {/* Consent card */}
            <div style={{
              background: 'rgba(96,165,250,0.06)',
              border: '1px solid rgba(96,165,250,0.2)',
              borderRadius: 12,
              padding: '1rem 1.25rem',
              marginBottom: '1.5rem',
              fontSize: '0.85rem',
              color: 'rgba(255,255,255,0.7)',
              lineHeight: 1.7,
            }}>
              <div style={{ fontWeight: 700, color: '#93c5fd', marginBottom: '0.5rem' }}>
                📋 Data Processing Notice
              </div>
              Your messages will be <strong style={{ color: '#fff' }}>securely processed</strong> by our VPS AI server.
              <ul style={{ marginTop: '0.5rem', paddingLeft: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                <li>End-to-end encrypted in transit</li>
                <li>Not stored or used for training</li>
                <li>VPS located in a privacy-respecting region</li>
                <li>You can switch to Local AI at any time</li>
              </ul>
            </div>

            <div style={{ display: 'flex', gap: '0.75rem' }}>
              <button
                id="consent-cancel-btn"
                onClick={() => setStep('main')}
                style={{
                  flex: 1, padding: '0.8rem',
                  borderRadius: 10,
                  background: 'transparent',
                  border: '1px solid rgba(255,255,255,0.1)',
                  color: 'rgba(255,255,255,0.5)',
                  fontSize: '0.875rem', fontWeight: 600,
                  cursor: 'pointer', fontFamily: 'inherit',
                  transition: 'all 0.15s',
                }}
                onMouseEnter={e => e.currentTarget.style.borderColor = 'rgba(255,255,255,0.25)'}
                onMouseLeave={e => e.currentTarget.style.borderColor = 'rgba(255,255,255,0.1)'}
              >
                ← Cancel
              </button>

              <button
                id="consent-accept-btn"
                onClick={handleConsent}
                style={{
                  flex: 2, padding: '0.8rem',
                  borderRadius: 10,
                  background: 'linear-gradient(135deg, #3b82f6 0%, #6366f1 100%)',
                  border: 'none',
                  color: '#fff',
                  fontSize: '0.875rem', fontWeight: 700,
                  cursor: 'pointer', fontFamily: 'inherit',
                  transition: 'all 0.2s ease',
                }}
                onMouseEnter={e => e.currentTarget.style.transform = 'translateY(-1px)'}
                onMouseLeave={e => e.currentTarget.style.transform = 'translateY(0)'}
              >
                ✅ Accept & Use Cloud AI
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
