import React, { useState, useEffect } from 'react';
import {
  adminListFinetuneSessions,
  adminCurateDataset,
  adminCreateCustomModel,
  getModels
} from '../services/api';

export default function FineTuneWizard() {
  const [step, setStep] = useState(1);
  const [sessions, setSessions] = useState([]);
  const [selectedSessionIds, setSelectedSessionIds] = useState([]);
  const [format, setFormat] = useState('alpaca');
  const [censorInput, setCensorInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [actionMsg, setActionMsg] = useState('');

  // Step 2 variables
  const [datasetResult, setDatasetResult] = useState(null);
  const [curating, setCurating] = useState(false);

  // Step 3 variables
  const [availableModels, setAvailableModels] = useState([]);
  const [baseModel, setBaseModel] = useState('');
  const [systemPrompt, setSystemPrompt] = useState('You are a helpful and polite Tamil AI assistant. Respond in clear Tamil.');
  const [temperature, setTemperature] = useState(0.7);
  const [newModelName, setNewModelName] = useState('tamil-custom-model');
  const [creatingModel, setCreatingModel] = useState(false);

  const notify = (msg) => {
    setActionMsg(msg);
    setTimeout(() => setActionMsg(''), 5000);
  };

  useEffect(() => {
    const init = async () => {
      try {
        const [sessionData, modelData] = await Promise.all([
          adminListFinetuneSessions(),
          getModels()
        ]);
        setSessions(sessionData.sessions || []);
        
        const localModels = modelData.local || [];
        setAvailableModels(localModels);
        if (localModels.length > 0) {
          setBaseModel(localModels[0]);
        } else {
          setBaseModel('llama3');
        }
      } catch (e) {
        notify(`⚠️ Failed to load setup data: ${e.message}`);
      } finally {
        setLoading(false);
      }
    };
    init();
  }, []);

  const handleSelectSession = (sid) => {
    setSelectedSessionIds(prev => 
      prev.includes(sid) ? prev.filter(id => id !== sid) : [...prev, sid]
    );
  };

  const handleSelectAll = () => {
    if (selectedSessionIds.length === sessions.length) {
      setSelectedSessionIds([]);
    } else {
      setSelectedSessionIds(sessions.map(s => s.session_id));
    }
  };

  const handleCurate = async () => {
    if (selectedSessionIds.length === 0) {
      notify('❌ Please select at least one session to curate.');
      return;
    }
    setCurating(true);
    try {
      const censorList = censorInput
        .split(',')
        .map(w => w.trim())
        .filter(w => w.length > 0);

      const result = await adminCurateDataset(selectedSessionIds, format, censorList);
      setDatasetResult(result);
      setStep(2);
    } catch (e) {
      notify(`❌ Curation failed: ${e.message}`);
    } finally {
      setCurating(false);
    }
  };

  const handleDownloadDataset = () => {
    if (!datasetResult || !datasetResult.dataset) return;
    const jsonString = JSON.stringify(datasetResult.dataset, null, 2);
    const blob = new Blob([jsonString], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `tamil_ai_training_dataset_${format}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    notify('✅ Dataset download started.');
  };

  const handleCreateModel = async (e) => {
    e.preventDefault();
    if (!newModelName.trim()) {
      notify('❌ Model name is required.');
      return;
    }
    setCreatingModel(true);
    try {
      const res = await adminCreateCustomModel(
        newModelName.trim(),
        baseModel,
        systemPrompt,
        parseFloat(temperature)
      );
      notify(`✅ ${res.message}`);
      setStep(4);
    } catch (e) {
      notify(`❌ Model creation failed: ${e.message}`);
    } finally {
      setCreatingModel(false);
    }
  };

  if (loading) {
    return <div style={{ color: 'var(--color-text-muted)', padding: '1.5rem' }}>Loading Fine-Tuning Curation Panel…</div>;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Notifications */}
      {actionMsg && (
        <div style={{
          padding: '0.75rem 1rem', borderRadius: 'var(--radius-md)',
          background: actionMsg.includes('❌') ? 'rgba(239,68,68,0.1)' : 'rgba(34,211,165,0.1)',
          border: `1px solid ${actionMsg.includes('❌') ? 'rgba(239,68,68,0.3)' : 'rgba(34,211,165,0.3)'}`,
          color: actionMsg.includes('❌') ? 'var(--color-error)' : 'var(--color-success)',
          fontSize: '0.875rem',
        }}>
          {actionMsg}
        </div>
      )}

      {/* Stepper Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: 'var(--color-surface-2)',
        padding: '1rem',
        borderRadius: 'var(--radius-md)',
        border: '1px solid var(--color-border)'
      }}>
        {[
          { num: 1, label: 'Curation' },
          { num: 2, label: 'Export' },
          { num: 3, label: 'Modelfile Creator' }
        ].map((s) => (
          <div key={s.num} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{
              width: '24px',
              height: '24px',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 700,
              fontSize: '0.75rem',
              background: step === s.num ? 'var(--color-accent)' : step > s.num ? 'var(--color-success)' : 'rgba(255,255,255,0.1)',
              color: 'white',
              transition: 'all 0.3s'
            }}>{step > s.num ? '✓' : s.num}</span>
            <span style={{
              fontSize: '0.85rem',
              fontWeight: step === s.num ? 600 : 400,
              color: step === s.num ? 'var(--color-text)' : 'var(--color-text-muted)'
            }}>{s.label}</span>
          </div>
        ))}
      </div>

      {/* STEP 1: CURATION */}
      {step === 1 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div className="card">
            <div className="card-title">💬 Select Conversations for Dataset</div>
            <p style={{ color: 'var(--color-text-muted)', fontSize: '0.82rem', marginTop: '-0.25rem', marginBottom: '1rem' }}>
              Select the best user chats to export as instruct tuning examples.
            </p>

            {sessions.length === 0 ? (
              <div style={{ color: 'var(--color-text-faint)', fontSize: '0.85rem', textAlign: 'center', padding: '2rem' }}>
                No active conversation history found to curate.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '300px', overflowY: 'auto', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', padding: '0.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.4rem 0.6rem', borderBottom: '1px solid var(--color-border)', fontWeight: 600 }}>
                  <input type="checkbox" checked={selectedSessionIds.length === sessions.length} onChange={handleSelectAll} />
                  <span style={{ fontSize: '0.82rem', flex: 1 }}>Session ID / Preview</span>
                  <span style={{ fontSize: '0.82rem', width: '80px', textAlign: 'right' }}>Turns</span>
                </div>
                {sessions.map((s) => (
                  <label key={s.session_id} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.4rem 0.6rem', cursor: 'pointer', borderRadius: 'var(--radius-md)', hover: { background: 'rgba(255,255,255,0.02)' } }}>
                    <input
                      type="checkbox"
                      checked={selectedSessionIds.includes(s.session_id)}
                      onChange={() => handleSelectSession(s.session_id)}
                    />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontWeight: 600, fontSize: '0.82rem', color: 'var(--color-accent-light)' }}>{s.session_id.substring(0, 12)}…</div>
                      <div style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.preview}</div>
                    </div>
                    <span style={{ fontSize: '0.8rem', color: 'var(--color-text-faint)', width: '80px', textAlign: 'right' }}>{s.message_count}</span>
                  </label>
                ))}
              </div>
            )}
            <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginTop: '0.5rem' }}>
              Selected: <strong>{selectedSessionIds.length}</strong> / {sessions.length} sessions
            </div>
          </div>

          <div className="card">
            <div className="card-title">🛡️ Dataset Curation Parameters</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '0.5rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.3rem' }}>Dataset Format</label>
                <div style={{ display: 'flex', gap: '1rem' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.82rem' }}>
                    <input type="radio" checked={format === 'alpaca'} onChange={() => setFormat('alpaca')} />
                    Alpaca JSON (instruction, input, output pairs)
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.82rem' }}>
                    <input type="radio" checked={format === 'sharegpt'} onChange={() => setFormat('sharegpt')} />
                    ShareGPT (conversational role-play format)
                  </label>
                </div>
              </div>

              <div>
                <label htmlFor="censor-input" style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.3rem' }}>Redact / Censor Words</label>
                <input
                  id="censor-input"
                  type="text"
                  placeholder="e.g. dev-local-key, myname, token123 (comma separated)"
                  value={censorInput}
                  onChange={(e) => setCensorInput(e.target.value)}
                  style={{
                    width: '100%',
                    background: 'var(--color-surface-3)',
                    border: '1px solid var(--color-border)',
                    color: 'var(--color-text)',
                    borderRadius: 'var(--radius-md)',
                    padding: '0.5rem 0.75rem',
                    fontFamily: 'inherit',
                    fontSize: '0.85rem'
                  }}
                />
                <span style={{ fontSize: '0.72rem', color: 'var(--color-text-faint)', marginTop: '0.2rem', display: 'block' }}>
                  Occurrences of these words in instructions and outputs will be replaced with <code>[CENSORED]</code>.
                </span>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button
              className="btn btn-primary"
              disabled={curating || selectedSessionIds.length === 0}
              onClick={handleCurate}
              style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
            >
              {curating ? 'Curating…' : 'Compile Dataset 🚀'}
            </button>
          </div>
        </div>
      )}

      {/* STEP 2: EXPORT */}
      {step === 2 && datasetResult && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div className="card">
            <div className="card-title">📊 Dataset Compilation Statistics</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem', marginTop: '0.5rem' }}>
              <div style={{ textAlign: 'center', padding: '0.75rem', background: 'rgba(255,255,255,0.02)', borderRadius: 'var(--radius-md)' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Output Format</div>
                <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--color-accent-light)', textTransform: 'uppercase' }}>{datasetResult.format}</div>
              </div>
              <div style={{ textAlign: 'center', padding: '0.75rem', background: 'rgba(255,255,255,0.02)', borderRadius: 'var(--radius-md)' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Instruct Items</div>
                <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--color-success)' }}>{datasetResult.item_count}</div>
              </div>
              <div style={{ textAlign: 'center', padding: '0.75rem', background: 'rgba(255,255,255,0.02)', borderRadius: 'var(--radius-md)' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Total Turns Read</div>
                <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--color-warning)' }}>{datasetResult.total_turns_processed}</div>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-title">📄 Dataset Preview</div>
            <pre style={{
              background: 'var(--color-surface-3)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-md)',
              padding: '1rem',
              color: 'var(--color-teal)',
              fontSize: '0.8rem',
              maxHeight: '200px',
              overflowY: 'auto',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-all',
              fontFamily: 'monospace'
            }}>
              {JSON.stringify(datasetResult.dataset, null, 2)}
            </pre>
            <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.75rem' }}>
              <button className="btn btn-primary" onClick={handleDownloadDataset}>
                💾 Download JSON Dataset
              </button>
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <button className="btn btn-ghost" onClick={() => setStep(1)}>
              ← Back to Curation
            </button>
            <button className="btn btn-primary" onClick={() => setStep(3)}>
              Proceed to Modelfile Creator →
            </button>
          </div>
        </div>
      )}

      {/* STEP 3: MODELFILE CREATOR */}
      {step === 3 && (
        <form onSubmit={handleCreateModel} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div className="card">
            <div className="card-title">🤖 Custom Modelfile Configuration</div>
            <p style={{ color: 'var(--color-text-muted)', fontSize: '0.82rem', marginTop: '-0.25rem', marginBottom: '1rem' }}>
              Ollama compiles fine-tuned instruction behavior via Docker-like Modelfiles.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div>
                  <label htmlFor="base-model-select" style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.3rem' }}>Base Model</label>
                  <select
                    id="base-model-select"
                    value={baseModel}
                    onChange={(e) => setBaseModel(e.target.value)}
                    style={{
                      width: '100%',
                      background: 'var(--color-surface-3)',
                      border: '1px solid var(--color-border)',
                      color: 'var(--color-text)',
                      borderRadius: 'var(--radius-md)',
                      padding: '0.5rem 0.75rem',
                      fontFamily: 'inherit',
                      fontSize: '0.85rem'
                    }}
                  >
                    {availableModels.map(m => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                    {!availableModels.includes('llama3') && <option value="llama3">llama3 (download if missing)</option>}
                    {!availableModels.includes('mistral') && <option value="mistral">mistral (download if missing)</option>}
                    {!availableModels.includes('tinyllama') && <option value="tinyllama">tinyllama (download if missing)</option>}
                  </select>
                </div>
                <div>
                  <label htmlFor="new-model-name" style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.3rem' }}>New Model Name</label>
                  <input
                    id="new-model-name"
                    type="text"
                    placeholder="e.g. tamil-helper-v1"
                    value={newModelName}
                    onChange={(e) => setNewModelName(e.target.value)}
                    style={{
                      width: '100%',
                      background: 'var(--color-surface-3)',
                      border: '1px solid var(--color-border)',
                      color: 'var(--color-text)',
                      borderRadius: 'var(--radius-md)',
                      padding: '0.5rem 0.75rem',
                      fontFamily: 'inherit',
                      fontSize: '0.85rem'
                    }}
                    required
                  />
                </div>
              </div>

              <div>
                <label htmlFor="system-prompt" style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.3rem' }}>System Instruction Prompt</label>
                <textarea
                  id="system-prompt"
                  rows={4}
                  value={systemPrompt}
                  onChange={(e) => setSystemPrompt(e.target.value)}
                  style={{
                    width: '100%',
                    background: 'var(--color-surface-3)',
                    border: '1px solid var(--color-border)',
                    color: 'var(--color-text)',
                    borderRadius: 'var(--radius-md)',
                    padding: '0.5rem 0.75rem',
                    fontFamily: 'inherit',
                    fontSize: '0.85rem',
                    resize: 'vertical'
                  }}
                  required
                />
                <span style={{ fontSize: '0.72rem', color: 'var(--color-text-faint)', marginTop: '0.2rem', display: 'block' }}>
                  This shapes the fundamental tone, language constraints (e.g. Tamil), and behavior of your custom assistant.
                </span>
              </div>

              <div>
                <label htmlFor="temp-slider" style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.3rem' }}>
                  <span>Temperature</span>
                  <span style={{ color: 'var(--color-accent-light)' }}>{temperature}</span>
                </label>
                <input
                  id="temp-slider"
                  type="range"
                  min="0.0"
                  max="1.5"
                  step="0.1"
                  value={temperature}
                  onChange={(e) => setTemperature(e.target.value)}
                  style={{ width: '100%', accentColor: 'var(--color-accent)' }}
                />
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <button type="button" className="btn btn-ghost" onClick={() => setStep(2)}>
              ← Back to Export
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={creatingModel}
              style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
            >
              {creatingModel ? 'Creating Model in Ollama…' : 'Compile & Generate Model 🛠️'}
            </button>
          </div>
        </form>
      )}

      {/* STEP 4: SUCCESS */}
      {step === 4 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', textAlign: 'center', padding: '2rem 1rem' }}>
          <div style={{ fontSize: '3.5rem', marginBottom: '0.5rem' }}>🎉</div>
          <h3 style={{ fontSize: '1.4rem', fontWeight: 700, color: 'var(--color-success)' }}>Custom Model Created!</h3>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.9rem', maxWidth: '500px', margin: '0 auto' }}>
            Your custom prompted model <strong>{newModelName}</strong> has been successfully built and registered in local Ollama.
            It will now be available in the Model Routing selection tabs or when communicating with the assistant.
          </p>
          <div style={{ marginTop: '1.5rem', display: 'flex', justify: 'center', gap: '1rem', justifyContent: 'center' }}>
            <button className="btn btn-primary" onClick={() => {
              setStep(1);
              setSelectedSessionIds([]);
              setDatasetResult(null);
            }}>
              Start New Curation
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
