import React, { useState, useEffect, useRef } from 'react';
import { getVoiceProfiles, enrollVoiceProfile, deleteVoiceProfile, getLockoutStatus, getVoiceAttempts, getVoiceSecurityMetrics } from '../services/api';

export default function VoiceSecurityPanel({ user }) {
  const [profiles, setProfiles] = useState([]);
  const [attempts, setAttempts] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [lockout, setLockout] = useState({ locked: false, locked_until: null });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');

  // Enrollment state
  const [profileName, setProfileName] = useState('');
  const [enrolling, setEnrolling] = useState(false);
  const [samples, setSamples] = useState([]); // Array of recorded blobs
  const [recording, setRecording] = useState(false);
  const [sampleIndex, setSampleIndex] = useState(0);

  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);

  const fetchInit = async () => {
    setLoading(true);
    try {
      const [profList, attemptsList, lockStatus, secMetrics] = await Promise.all([
        getVoiceProfiles(),
        getVoiceAttempts(10),
        getLockoutStatus(),
        getVoiceSecurityMetrics()
      ]);
      setProfiles(profList.profiles || []);
      setAttempts(attemptsList.attempts || []);
      setLockout(lockStatus);
      setMetrics(secMetrics);
    } catch (err) {
      setError('❌ Failed to fetch voice security details: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInit();
  }, []);

  const handleStartRecord = async () => {
    audioChunksRef.current = [];
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      
      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(audioChunksRef.current, { type: 'audio/wav' });
        setSamples(prev => [...prev, blob]);
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorder.start();
      setRecording(true);
    } catch (err) {
      setError('❌ Microphone access denied: ' + err.message);
    }
  };

  const handleStopRecord = () => {
    if (mediaRecorderRef.current && recording) {
      mediaRecorderRef.current.stop();
      setRecording(false);
    }
  };

  const handleClearSamples = () => {
    setSamples([]);
    setError('');
  };

  const handleEnroll = async (e) => {
    e.preventDefault();
    if (samples.length < 3) {
      setError('❌ Please record at least 3 audio samples first.');
      return;
    }
    if (!profileName.trim()) {
      setError('❌ Please specify a profile name.');
      return;
    }

    setEnrolling(true);
    setError('');
    setMsg('');
    try {
      const targetUserId = user?.id || 'admin-user-123';
      await enrollVoiceProfile(profileName.trim(), targetUserId, samples);
      setMsg('✅ Voice profile calibrated and enrolled successfully.');
      setProfileName('');
      setSamples([]);
      fetchInit();
    } catch (err) {
      setError('❌ Calibration failed: ' + err.message);
    } finally {
      setEnrolling(false);
    }
  };

  const handleDeleteProfile = async (id) => {
    if (!confirm('Are you sure you want to revoke this biometric profile?')) return;
    try {
      await deleteVoiceProfile(id);
      setMsg('✅ Voice profile revoked successfully.');
      fetchInit();
    } catch (err) {
      setError('❌ Failed to revoke profile: ' + err.message);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', height: '100%', overflowY: 'auto', padding: '2rem' }}>
      <div>
        <h2 style={{ fontSize: '1.6rem', fontWeight: 800, background: 'linear-gradient(135deg, var(--color-accent-light), var(--color-teal))', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          🔒 Voice Biometrics & Security
        </h2>
        <p style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem', marginTop: '0.2rem' }}>
          Enroll speaker templates, view verified profiles, verify challenge statuses, and check lockout safety parameters.
        </p>
      </div>

      {error && (
        <div style={{ padding: '0.75rem 1rem', borderRadius: 'var(--radius-md)', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', color: 'var(--color-error)', fontSize: '0.875rem' }}>
          {error}
        </div>
      )}

      {msg && (
        <div style={{ padding: '0.75rem 1rem', borderRadius: 'var(--radius-md)', background: 'rgba(34,211,165,0.1)', border: '1px solid rgba(34,211,165,0.3)', color: 'var(--color-success)', fontSize: '0.875rem' }}>
          {msg}
        </div>
      )}

      {lockout.locked && (
        <div style={{ padding: '1rem', border: '1px solid rgba(239,68,68,0.3)', background: 'rgba(239,68,68,0.08)', color: 'var(--color-error)', borderRadius: '12px' }}>
          <h4 style={{ margin: 0, fontWeight: 700, fontSize: '0.9rem' }}>⚠️ Biometric Account Lockout Active</h4>
          <p style={{ margin: '0.2rem 0 0', fontSize: '0.78rem', opacity: 0.9 }}>
            Voice biometrics verification has failed multiple challenge checks. Locked until: {new Date(lockout.locked_until).toLocaleString()}.
          </p>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.5rem', alignItems: 'flex-start' }}>
        {/* Enrollment Form */}
        <div className="card" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: '18px', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--color-text)', borderBottom: '1px solid var(--color-border)', paddingBottom: '0.5rem', margin: 0 }}>
            🎙️ Biometric Voice Enrollment
          </h3>

          {user?.role === 'guest' ? (
            <div style={{ padding: '1rem', background: 'var(--color-surface-2)', borderRadius: '8px', fontSize: '0.82rem', color: 'var(--color-text-faint)' }}>
              🔒 Guest mode accounts are restricted from enrolling biometric profile templates. Please register / login.
            </div>
          ) : (
            <form onSubmit={handleEnroll} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-text-muted)', marginBottom: '0.4rem' }}>Profile Name / Identifier</label>
                <input type="text" value={profileName} onChange={e => setProfileName(e.target.value)} placeholder="e.g. Primary Voice, Office Mic" required style={{ width: '100%', padding: '0.5rem 0.75rem', borderRadius: '8px', border: '1px solid var(--color-border)', background: 'var(--color-surface-2)', color: 'var(--color-text)' }} />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-text-muted)', marginBottom: '0.4rem' }}>Record 3 Audio Calibration Samples ({samples.length}/3)</label>
                
                <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem', flexWrap: 'wrap' }}>
                  <button type="button" disabled={recording || samples.length >= 3} className="btn btn-primary" onClick={handleStartRecord} style={{ fontSize: '0.8rem', padding: '0.4rem 1rem' }}>
                    🎙️ Record Sample {samples.length + 1}
                  </button>
                  {recording && (
                    <button type="button" className="btn btn-danger" onClick={handleStopRecord} style={{ fontSize: '0.8rem', padding: '0.4rem 1rem' }}>
                      🔴 Stop Recording
                    </button>
                  )}
                  {samples.length > 0 && (
                    <button type="button" className="btn btn-ghost" onClick={handleClearSamples} style={{ fontSize: '0.8rem', padding: '0.4rem 1rem' }}>
                      🧹 Clear
                    </button>
                  )}
                </div>
                
                <div style={{ display: 'flex', gap: '0.25rem', marginTop: '0.75rem' }}>
                  {[0, 1, 2].map(i => (
                    <div key={i} style={{ flex: 1, height: '6px', borderRadius: '3px', background: samples.length > i ? 'var(--color-success)' : 'var(--color-surface-2)', border: '1px solid var(--color-border)' }} />
                  ))}
                </div>
              </div>

              <button type="submit" disabled={enrolling || samples.length < 3 || !profileName.trim()} className="btn btn-primary" style={{ width: '100%', marginTop: '0.5rem' }}>
                {enrolling ? '🛠️ Calibrating Voice signature...' : '🔒 Submit Enrollment'}
              </button>
            </form>
          )}
        </div>

        {/* Active Profiles */}
        <div className="card" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: '18px', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem', minHeight: '300px' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--color-text)', borderBottom: '1px solid var(--color-border)', paddingBottom: '0.5rem', margin: 0 }}>
            🛡️ Enrolled Voice Profiles
          </h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {profiles.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--color-text-faint)', fontSize: '0.82rem' }}>
                No active biometrics signature profiles registered.
              </div>
            ) : (
              profiles.map(p => (
                <div key={p.id} style={{ padding: '0.75rem', borderRadius: '10px', background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <div style={{ fontWeight: 700, color: 'var(--color-text)', fontSize: '0.85rem' }}>{p.profile_name}</div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--color-text-faint)', marginTop: '0.2rem' }}>
                      ID: {p.id.slice(0, 12)}… · Status: <span style={{ color: 'var(--color-success)' }}>{p.status.toUpperCase()}</span>
                    </div>
                    <div style={{ fontSize: '0.68rem', color: 'var(--color-text-muted)', marginTop: '0.2rem' }}>
                      Threshold: Adaptive ({p.adaptive_threshold}) · Confidence: {Math.round(p.enrollment_mean * 100)}%
                    </div>
                  </div>
                  <button className="btn btn-danger" onClick={() => handleDeleteProfile(p.id)} style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}>
                    Revoke
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Verification Timeline */}
      <div className="card" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', padding: '1.5rem', borderRadius: '18px', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--color-text)', borderBottom: '1px solid var(--color-border)', paddingBottom: '0.5rem', margin: 0 }}>
          Timeline of Recent Verification Attempts
        </h3>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.82rem' }}>
            <thead>
              <tr style={{ color: 'var(--color-text-muted)', borderBottom: '1px solid var(--color-border)' }}>
                <th style={{ padding: '0.5rem' }}>Timestamp</th>
                <th style={{ padding: '0.5rem' }}>Confidence</th>
                <th style={{ padding: '0.5rem' }}>Challenge digits</th>
                <th style={{ padding: '0.5rem' }}>Status result</th>
              </tr>
            </thead>
            <tbody>
              {attempts.length === 0 ? (
                <tr>
                  <td colSpan={4} style={{ textAlign: 'center', padding: '1.5rem', color: 'var(--color-text-faint)' }}>No authentication logs available.</td>
                </tr>
              ) : (
                attempts.map(att => (
                  <tr key={att.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.03)', color: 'var(--color-text)' }}>
                    <td style={{ padding: '0.5rem', fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>{new Date(att.created_at).toLocaleString()}</td>
                    <td style={{ padding: '0.5rem' }}>{Math.round(att.confidence_score * 100)}%</td>
                    <td style={{ padding: '0.5rem' }}>{att.challenge_required ? '🔢 3-Digit verification' : 'Biometric match only'}</td>
                    <td style={{ padding: '0.5rem' }}>
                      <span style={{
                        padding: '1px 6px', borderRadius: '4px', fontSize: '0.72rem', fontWeight: 600,
                        background: att.verification_status === 'authorized' ? 'rgba(34,211,165,0.1)' : 'rgba(239,68,68,0.1)',
                        color: att.verification_status === 'authorized' ? 'var(--color-success)' : 'var(--color-error)'
                      }}>
                        {att.verification_status.toUpperCase()}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
