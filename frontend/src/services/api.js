/**
 * Phase 2 API additions + Phase 4 Hybrid Runtime additions
 */

const BASE = 'http://localhost:8000/api';

async function request(method, path, body = null, isFormData = false) {
  const opts = {
    method,
    headers: isFormData ? {} : { 'Content-Type': 'application/json' },
  };
  if (body) opts.body = isFormData ? body : JSON.stringify(body);
  const res = await fetch(`${BASE}${path}`, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Chat ─────────────────────────────────────────────────────────────────────
export const sendMessage = (message, sessionId) =>
  request('POST', '/chat', { message, session_id: sessionId });

// ── Agent ─────────────────────────────────────────────────────────────────────
export const runAgent = (query, sessionId, forceAgent = false) =>
  request('POST', '/agent/run', { query, session_id: sessionId, force_agent: forceAgent });

// ── Tamil Intelligence ────────────────────────────────────────────────────────
export const normalizeTamil = (text) =>
  request('POST', '/tamil/normalize', { text });

export const tanglishToTamil = (text) =>
  request('POST', '/tamil/tanglish-to-tamil', { text });

// ── Upload ────────────────────────────────────────────────────────────────────
export const uploadFile = (file) => {
  const form = new FormData();
  form.append('file', file);
  return request('POST', '/upload', form, true);
};
export const listFiles = () => request('GET', '/files');
export const deleteFile = (filename) => request('DELETE', `/files/${filename}`);

// ── RAG ───────────────────────────────────────────────────────────────────────
export const queryRAG = (query, topK = 5) =>
  request('POST', '/rag/query', { query, top_k: topK });
export const ragStats = () => request('GET', '/rag/stats');
export const ragReset = () => request('POST', '/rag/reset');

// ── Metrics ───────────────────────────────────────────────────────────────────
export const getMetrics = () => request('GET', '/metrics');
export const setModelOverride = (model) =>
  request('POST', `/metrics/model-override${model ? `?model=${model}` : ''}`);

// ── Admin ─────────────────────────────────────────────────────────────────────
export const systemStatus = () => request('GET', '/admin/status');
export const retrain = () => request('POST', '/admin/retrain');
export const clearMemory = () => request('POST', '/admin/clear-memory');
export const clearCache = () => request('POST', '/admin/clear-cache');

// ── Audio (Voice AI) ──────────────────────────────────────────────────────────
export const transcribeAudio = (audioBlob, language = null) => {
  const form = new FormData();
  form.append('audio', audioBlob, 'recording.wav');
  if (language) form.append('language', language);
  return request('POST', '/audio/transcribe', form, true);
};

export const generateSpeech = async (text, language = 'ta') => {
  const res = await fetch(`${BASE}/audio/speak`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, language }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.blob();
};

// ── Memory (Task 3) ───────────────────────────────────────────────────────────
export const getMemories = (userId, category = null) => {
  const qs = category ? `?category=${category}` : '';
  return request('GET', `/memory/${userId}${qs}`);
};

export const saveMemory = (userId, key, value, category = 'user_fact', tags = []) =>
  request('POST', `/memory/${userId}`, { key, value, category, tags });

export const deleteMemory = (userId, factId) =>
  request('DELETE', `/memory/${userId}/${factId}`);

export const deleteAllMemories = (userId) =>
  request('DELETE', `/memory/${userId}`);

export const searchMemory = (userId, q) =>
  request('GET', `/memory/${userId}/search?q=${encodeURIComponent(q)}`);

// ── Admin Memory ──────────────────────────────────────────────────────────────
export const adminGetAllMemories = (limit = 200) =>
  request('GET', `/admin/memories?limit=${limit}`);

export const adminDeleteUserMemories = (userId) =>
  request('DELETE', `/admin/memories/${userId}`);

export const adminPurgeAllMemories = () =>
  request('DELETE', `/admin/memories`);

export const adminMemoryStats = () =>
  request('GET', `/admin/memory-stats`);

// ── Runtime (Phase 4) ─────────────────────────────────────────────────────────
export const getRuntimeStatus = () =>
  request('GET', '/runtime/status');

export const setRuntimeMode = (mode) =>
  request('POST', '/runtime/mode', { mode });

export const setRuntimeModel = (model) =>
  request('POST', '/runtime/model', { model });

export const getModels = () =>
  request('GET', '/models');

export const refreshRuntime = () =>
  request('POST', '/runtime/refresh');

export const adminRuntimeDashboard = () =>
  request('GET', '/admin/runtime');
