import React, { useState, useEffect } from 'react';
import { getDevicesList, getCommandsList, createCommand } from '../services/api';

export default function AutomationPage() {
  const [devices, setDevices] = useState([]);
  const [commands, setCommands] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  
  // Schedule Form State
  const [selectedDevice, setSelectedDevice] = useState('');
  const [tool, setTool] = useState('desktop.open_app');
  const [params, setParams] = useState('{"app": "vscode"}');
  const [rawInput, setRawInput] = useState('Open VS Code');
  const [delayMinutes, setDelayMinutes] = useState(0);
  const [scheduling, setScheduling] = useState(false);
  const [msg, setMsg] = useState('');

  const fetchInit = async () => {
    setLoading(true);
    try {
      const [devList, cmdList] = await Promise.all([
        getDevicesList(),
        getCommandsList(50)
      ]);
      setDevices(devList || []);
      setCommands(cmdList || []);
      if (devList && devList.length > 0) {
        setSelectedDevice(devList[0].id);
      }
    } catch (err) {
      setError('❌ Failed to fetch automation data: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInit();
    const interval = setInterval(async () => {
      try {
        const cmdList = await getCommandsList(50);
        setCommands(cmdList || []);
      } catch {}
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleEnqueue = async (e) => {
    e.preventDefault();
    if (!selectedDevice) {
      setError('❌ No target device selected.');
      return;
    }
    
    let parsedParams = {};
    try {
      parsedParams = JSON.parse(params);
    } catch (err) {
      setError('❌ Invalid parameters JSON format: ' + err.message);
      return;
    }

    setScheduling(true);
    setError('');
    setMsg('');
    try {
      await createCommand(selectedDevice, tool, parsedParams, rawInput);
      setMsg('✅ Command successfully enqueued to agent workspace pipeline.');
      // Refresh list
      const cmdList = await getCommandsList(50);
      setCommands(cmdList || []);
    } catch (err) {
      setError('❌ Failed to enqueue command: ' + err.message);
    } finally {
      setScheduling(false);
    }
  };

  return (
    <div style={{ padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1.5rem', overflowY: 'auto', height: '100%' }}>
      <div>
        <h2 style={{ fontSize: '1.6rem', fontWeight: 800, background: 'linear-gradient(135deg, var(--color-accent-light), var(--color-teal))', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          ⚙️ Automation Center
        </h2>
        <p style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem', marginTop: '0.2rem' }}>
          Schedule and queue tool-based jobs on your registered desktop and mobile agent runtimes.
        </p>
      </div>

      {/* Warning regarding missing native Crontab Backend */}
      <div style={{ padding: '1rem', border: '1px solid rgba(245,158,11,0.3)', background: 'rgba(245,158,11,0.06)', borderRadius: '14px', display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
        <div style={{ fontSize: '1.5rem', marginTop: '-2px' }}>⚠️</div>
        <div>
          <h4 style={{ margin: 0, fontWeight: 700, fontSize: '0.88rem', color: 'var(--color-warning)' }}>
            System Status: Automation Backend is MISSING
          </h4>
          <p style={{ margin: '0.2rem 0 0', fontSize: '0.78rem', color: 'var(--color-text-muted)', lineHeight: 1.5 }}>
            Native Crontab recurring scheduler tasks are not configured in the FastAPI routes layer. 
            All jobs are enqueued directly into the **Live Agent Command Queue** (`/api/v1/commands/create`) for active background execution.
          </p>
        </div>
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

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.5rem', alignItems: 'flex-start' }}>
        {/* Enqueuer Form */}
        <form onSubmit={handleEnqueue} className="card" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', padding: '1.5rem', borderRadius: '18px', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--color-text)', borderBottom: '1px solid var(--color-border)', paddingBottom: '0.5rem', margin: 0 }}>
            Dispatch Agent Command
          </h3>

          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-text-muted)', marginBottom: '0.4rem' }}>Target Device</label>
            {devices.length === 0 ? (
              <div style={{ fontSize: '0.8rem', color: 'var(--color-text-faint)' }}>No online devices detected. Register agent first.</div>
            ) : (
              <select value={selectedDevice} onChange={e => setSelectedDevice(e.target.value)} style={{ width: '100%', padding: '0.5rem 0.75rem', borderRadius: '8px', border: '1px solid var(--color-border)', background: 'var(--color-surface-2)', color: 'var(--color-text)' }}>
                {devices.map(d => (
                  <option key={d.id} value={d.id}>{d.device_name || d.id} ({d.computed_status || d.status})</option>
                ))}
              </select>
            )}
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-text-muted)', marginBottom: '0.4rem' }}>Tool Method</label>
            <select value={tool} onChange={e => setTool(e.target.value)} style={{ width: '100%', padding: '0.5rem 0.75rem', borderRadius: '8px', border: '1px solid var(--color-border)', background: 'var(--color-surface-2)', color: 'var(--color-text)' }}>
              <option value="desktop.open_app">🖥️ desktop.open_app (Safe)</option>
              <option value="desktop.list_apps">🖥️ desktop.list_apps (Safe)</option>
              <option value="browser.open">🌐 browser.open (Safe)</option>
              <option value="browser.search">🌐 browser.search (Safe)</option>
              <option value="files.list">📁 files.list (Safe)</option>
              <option value="files.read">📄 files.read (Safe)</option>
              <option value="files.search">🔍 files.search (Safe)</option>
            </select>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-text-muted)', marginBottom: '0.4rem' }}>Original Raw Text Prompt</label>
            <input type="text" value={rawInput} onChange={e => setRawInput(e.target.value)} placeholder="e.g. Open VS Code workspace" style={{ width: '100%', padding: '0.5rem 0.75rem', borderRadius: '8px', border: '1px solid var(--color-border)', background: 'var(--color-surface-2)', color: 'var(--color-text)' }} />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-text-muted)', marginBottom: '0.4rem' }}>Parameters (JSON Format)</label>
            <textarea value={params} onChange={e => setParams(e.target.value)} placeholder='{"app": "vscode"}' rows={3} style={{ width: '100%', padding: '0.5rem 0.75rem', borderRadius: '8px', border: '1px solid var(--color-border)', background: 'var(--color-surface-2)', color: 'var(--color-text)', fontFamily: 'var(--font-mono)', fontSize: '0.8rem', resize: 'vertical' }} />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-text-muted)', marginBottom: '0.4rem' }}>Execution Delay (Simulation)</label>
            <select value={delayMinutes} onChange={e => setDelayMinutes(Number(e.target.value))} style={{ width: '100%', padding: '0.5rem 0.75rem', borderRadius: '8px', border: '1px solid var(--color-border)', background: 'var(--color-surface-2)', color: 'var(--color-text)' }}>
              <option value={0}>Run Immediately (Real-time dispatch)</option>
              <option value={5}>Schedule in 5 Minutes (Client-delayed)</option>
              <option value={15}>Schedule in 15 Minutes (Client-delayed)</option>
            </select>
          </div>

          <button type="submit" disabled={scheduling || devices.length === 0} className="btn btn-primary" style={{ width: '100%', marginTop: '0.5rem' }}>
            {scheduling ? 'Enqueuing...' : '🚀 Queue Command'}
          </button>
        </form>

        {/* Command Log */}
        <div className="card" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', padding: '1.5rem', borderRadius: '18px', display: 'flex', flexDirection: 'column', gap: '1rem', minHeight: '400px' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--color-text)', borderBottom: '1px solid var(--color-border)', paddingBottom: '0.5rem', margin: 0 }}>
            Recent Dispatch Logs
          </h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxHeight: '420px', overflowY: 'auto' }}>
            {commands.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--color-text-faint)', fontSize: '0.85rem' }}>
                No background tasks enqueued yet.
              </div>
            ) : (
              commands.map(cmd => (
                <div key={cmd.id} style={{ padding: '0.75rem', borderRadius: '10px', background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8rem' }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                      <span style={{ fontWeight: 700, color: 'var(--color-accent-light)', fontFamily: 'var(--font-mono)', fontSize: '0.72rem' }}>{cmd.id.slice(0, 8)}</span>
                      <span style={{
                        padding: '1px 6px', borderRadius: '4px', fontSize: '0.65rem', fontWeight: 600,
                        background: cmd.status === 'completed' ? 'rgba(34,211,165,0.1)' : cmd.status === 'failed' ? 'rgba(239,68,68,0.1)' : 'rgba(245,158,11,0.1)',
                        color: cmd.status === 'completed' ? 'var(--color-success)' : cmd.status === 'failed' ? 'var(--color-error)' : 'var(--color-warning)'
                      }}>
                        {cmd.status.toUpperCase()}
                      </span>
                    </div>
                    <div style={{ fontWeight: 600, marginTop: '0.25rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--color-text)' }}>
                      {cmd.raw_input || cmd.tool}
                    </div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--color-text-faint)', marginTop: '0.2rem' }}>
                      Target: {cmd.device_id.slice(0, 12)}… · Tool: {cmd.tool}
                    </div>
                  </div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--color-text-faint)', textAlign: 'right' }}>
                    {cmd.created_at ? new Date(cmd.created_at).toLocaleTimeString() : ''}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
