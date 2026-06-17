import React, { useState, useEffect } from 'react';
import { getSkills, saveSkill, deleteSkill, activateSkill } from '../services/api';
import RoleGuard from './RoleGuard';

export default function SkillsPage({ user, sessionId }) {
  const [skills, setSkills] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeSkillId, setActiveSkillId] = useState(null);
  
  // Custom Skill Form State
  const [showForm, setShowForm] = useState(false);
  const [skillId, setSkillId] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState('Developer');
  const [systemPrompt, setSystemPrompt] = useState('');
  const [model, setModel] = useState('auto');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchSkills();
  }, []);

  const fetchSkills = async () => {
    setLoading(true);
    try {
      const data = await getSkills();
      setSkills(data);
      // Find active skill from SQLite database via active_skill_id
      const active = data.find(s => s.is_active);
      if (active) setActiveSkillId(active.id);
    } catch (err) {
      setError('❌ Failed to load skills: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleActivate = async (id) => {
    const isActivating = activeSkillId !== id;
    const targetId = isActivating ? id : null;
    try {
      await activateSkill(sessionId, targetId);
      setActiveSkillId(targetId);
      // update local status
      setSkills(prev => prev.map(s => ({ ...s, is_active: s.id === targetId })));
    } catch (err) {
      setError('❌ Failed to activate skill: ' + err.message);
    }
  };

  const handleSaveSkill = async (e) => {
    e.preventDefault();
    if (!skillId.trim() || !name.trim() || !systemPrompt.trim()) return;
    setSaving(true);
    setError('');
    try {
      await saveSkill({
        id: skillId.trim(),
        name: name.trim(),
        description: description.trim(),
        category,
        system_prompt: systemPrompt.trim(),
        model,
        tools: { allow: [], deny: [] },
        memory_scope: ['project_context']
      });
      setShowForm(false);
      setSkillId('');
      setName('');
      setDescription('');
      setSystemPrompt('');
      fetchSkills();
    } catch (err) {
      setError('❌ ' + err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteSkill = async (id) => {
    if (!confirm(`Are you sure you want to delete custom skill "${id}"?`)) return;
    try {
      await deleteSkill(id);
      fetchSkills();
    } catch (err) {
      setError('❌ ' + err.message);
    }
  };

  return (
    <div style={{ padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1.5rem', overflowY: 'auto', height: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: '1.6rem', fontWeight: 800, background: 'linear-gradient(135deg, var(--color-accent-light), var(--color-teal))', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
            🎯 Skills Marketplace
          </h2>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem', marginTop: '0.2rem' }}>
            Customize your Rudran assistant personality, tools, and model routing parameters.
          </p>
        </div>
        <button 
          className="btn btn-primary"
          onClick={() => setShowForm(!showForm)}
        >
          {showForm ? '✕ Close Form' : '➕ Create Custom Skill'}
        </button>
      </div>

      {error && (
        <div style={{ padding: '0.75rem 1rem', borderRadius: 'var(--radius-md)', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', color: 'var(--color-error)', fontSize: '0.875rem' }}>
          {error}
        </div>
      )}

      {showForm && (
        <form onSubmit={handleSaveSkill} className="card" style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderRadius: '16px', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--color-text)' }}>Create Custom Agent Skill</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-text-muted)', marginBottom: '0.4rem' }}>Skill Identifier (Slug, lowercase-hyphen)</label>
              <input type="text" value={skillId} onChange={e => setSkillId(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))} placeholder="e.g. math-tutor" required style={{ width: '100%', padding: '0.5rem 0.75rem', borderRadius: '8px', border: '1px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-text)' }} />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-text-muted)', marginBottom: '0.4rem' }}>Skill Display Name</label>
              <input type="text" value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Mathematics Tutor" required style={{ width: '100%', padding: '0.5rem 0.75rem', borderRadius: '8px', border: '1px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-text)' }} />
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-text-muted)', marginBottom: '0.4rem' }}>Category</label>
              <select value={category} onChange={e => setCategory(e.target.value)} style={{ width: '100%', padding: '0.5rem 0.75rem', borderRadius: '8px', border: '1px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-text)' }}>
                <option value="Developer">💻 Developer</option>
                <option value="Teacher">🎓 Teacher</option>
                <option value="Creative">🎨 Creative</option>
                <option value="General">💼 General</option>
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-text-muted)', marginBottom: '0.4rem' }}>Model Override</label>
              <select value={model} onChange={e => setModel(e.target.value)} style={{ width: '100%', padding: '0.5rem 0.75rem', borderRadius: '8px', border: '1px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-text)' }}>
                <option value="auto">Auto (Dynamic router)</option>
                <option value="tinyllama">TinyLlama (Fast CPU)</option>
                <option value="mistral">Mistral (Balanced)</option>
                <option value="llama3">Llama3 (Advanced)</option>
                <option value="qwen2.5:3b">Qwen2.5:3b (Code/Complex)</option>
              </select>
            </div>
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-text-muted)', marginBottom: '0.4rem' }}>Short Description</label>
            <input type="text" value={description} onChange={e => setDescription(e.target.value)} placeholder="What is the skill role?" style={{ width: '100%', padding: '0.5rem 0.75rem', borderRadius: '8px', border: '1px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-text)' }} />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-text-muted)', marginBottom: '0.4rem' }}>System Prompt (Personality & Bounds)</label>
            <textarea value={systemPrompt} onChange={e => setSystemPrompt(e.target.value)} placeholder="Explain the role, tone, language hint, guidelines..." rows={4} required style={{ width: '100%', padding: '0.5rem 0.75rem', borderRadius: '8px', border: '1px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-text)', fontFamily: 'inherit', resize: 'vertical' }} />
          </div>
          <button type="submit" disabled={saving} className="btn btn-primary" style={{ alignSelf: 'flex-start' }}>
            {saving ? 'Creating...' : 'Create Skill Profile'}
          </button>
        </form>
      )}

      {loading ? (
        <div style={{ color: 'var(--color-text-muted)' }}>Loading skills catalog...</div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '1.25rem' }}>
          {skills.map(skill => (
            <div key={skill.id} className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', border: skill.id === activeSkillId ? '1px solid var(--color-accent)' : '1px solid var(--color-border)', background: 'var(--color-surface)', padding: '1.25rem', borderRadius: '16px', transition: 'all 0.2s', boxShadow: skill.id === activeSkillId ? '0 0 20px rgba(124, 92, 252, 0.15)' : 'none' }}>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <h4 style={{ margin: 0, fontWeight: 700, fontSize: '1.05rem', color: 'var(--color-text)' }}>{skill.name}</h4>
                  <span style={{ fontSize: '0.7rem', padding: '2px 8px', borderRadius: '999px', background: skill.is_builtin ? 'rgba(34,211,165,0.1)' : 'rgba(124,92,252,0.1)', color: skill.is_builtin ? 'var(--color-success)' : 'var(--color-accent-light)', border: `1px solid ${skill.is_builtin ? 'rgba(34,211,165,0.2)' : 'rgba(124,92,252,0.2)'}` }}>
                    {skill.is_builtin ? 'builtin' : 'custom'}
                  </span>
                </div>
                <div style={{ fontSize: '0.72rem', color: 'var(--color-text-faint)', marginTop: '0.2rem', textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 600 }}>
                  📂 {skill.category} · 🤖 {skill.model}
                </div>
                <p style={{ fontSize: '0.82rem', color: 'var(--color-text-muted)', marginTop: '0.5rem', lineHeight: 1.5, minHeight: '3rem' }}>
                  {skill.description || 'No description provided.'}
                </p>
                <div style={{ background: 'var(--color-surface-2)', padding: '0.5rem', borderRadius: '8px', border: '1px solid var(--color-border)', marginTop: '0.5rem' }}>
                  <div style={{ fontSize: '0.68rem', color: 'var(--color-text-faint)', fontWeight: 700, textTransform: 'uppercase' }}>System Instructions</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden', fontStyle: 'italic', marginTop: '0.2rem' }}>
                    "{skill.system_prompt}"
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--color-border)', paddingTop: '0.75rem', marginTop: '1rem' }}>
                <button
                  className={`btn ${skill.id === activeSkillId ? 'btn-ghost' : 'btn-primary'}`}
                  style={{ padding: '0.35rem 1rem', fontSize: '0.8rem' }}
                  onClick={() => handleActivate(skill.id)}
                >
                  {skill.id === activeSkillId ? '🟢 Deactivate' : '🔌 Activate'}
                </button>
                {!skill.is_builtin && (
                  <RoleGuard user={user} allowedRoles={['admin']}>
                    <button
                      className="btn btn-danger"
                      style={{ padding: '0.35rem 0.75rem', fontSize: '0.8rem' }}
                      onClick={() => handleDeleteSkill(skill.id)}
                    >
                      🗑️ Delete
                    </button>
                  </RoleGuard>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
