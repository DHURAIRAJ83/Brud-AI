/**
 * Phase 5 API — JWT auth header injection + Conversations + WebSocket helper
 */

const BASE = '/api';

export function getToken() {
  return localStorage.getItem('auth_token') || null;
}

export function getCsrfToken() {
  return localStorage.getItem('csrf_token') || null;
}

let refreshPromise = null;

export async function getOrPerformTokenRefresh() {
  if (refreshPromise) {
    return refreshPromise;
  }
  
  refreshPromise = (async () => {
    try {
      const csrfToken = getCsrfToken();
      if (!csrfToken) {
        throw new Error("No CSRF token for refresh");
      }
      
      const res = await fetch(`${BASE}/auth/refresh`, {
        method: 'POST',
        headers: {
          'X-CSRF-Token': csrfToken
        },
        credentials: 'include'
      });
      
      if (!res.ok) {
        throw new Error("Refresh token call failed");
      }
      
      const data = await res.json();
      if (data.access_token) {
        localStorage.setItem('auth_token', data.access_token);
      }
      if (data.csrf_token) {
        localStorage.setItem('csrf_token', data.csrf_token);
      }
      if (data.user) {
        localStorage.setItem('auth_user', JSON.stringify(data.user));
      }
      return data.access_token;
    } finally {
      refreshPromise = null;
    }
  })();
  
  return refreshPromise;
}

export function handleAuthExpiry() {
  localStorage.removeItem('auth_token');
  localStorage.removeItem('auth_user');
  localStorage.removeItem('csrf_token');
  window.dispatchEvent(new Event('auth-logout'));
}

async function requestRaw(method, path, body = null, isFormData = false, isBlob = false) {
  const token = getToken();
  const csrfToken = getCsrfToken();
  const headers = isFormData ? {} : { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (csrfToken && ['POST', 'PUT', 'DELETE', 'PATCH'].includes(method.toUpperCase())) {
    headers['X-CSRF-Token'] = csrfToken;
  }
  const opts = { 
    method, 
    headers,
    credentials: 'include'
  };
  if (body) opts.body = isFormData ? body : JSON.stringify(body);
  
  let res = await fetch(`${BASE}${path}`, opts);
  
  if (res.status === 401) {
    if (
      !path.startsWith('/auth/login') &&
      !path.startsWith('/auth/register') &&
      !path.startsWith('/auth/refresh') &&
      !path.startsWith('/auth/logout')
    ) {
      if (csrfToken) {
        try {
          const newToken = await getOrPerformTokenRefresh();
          const retryHeaders = { ...headers };
          retryHeaders['Authorization'] = `Bearer ${newToken}`;
          const newCsrf = getCsrfToken();
          if (newCsrf && ['POST', 'PUT', 'DELETE', 'PATCH'].includes(method.toUpperCase())) {
            retryHeaders['X-CSRF-Token'] = newCsrf;
          }
          const retryOpts = { ...opts, headers: retryHeaders };
          res = await fetch(`${BASE}${path}`, retryOpts);
        } catch (refreshErr) {
          console.error("Token refresh failed. Logging out...", refreshErr);
          handleAuthExpiry();
          throw refreshErr;
        }
      }
    }
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  
  return isBlob ? res.blob() : res.json();
}

export async function request(method, path, body = null, isFormData = false) {
  return requestRaw(method, path, body, isFormData, false);
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

// ── TanglishToTamil ───────────────────────────────────────────────────────────
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
  return requestRaw('POST', '/audio/speak', { text, language }, false, true);
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

// ── Plugins (Phase 5) ──────────────────────────────────────────────────────────
export const adminListPlugins = () =>
  request('GET', '/admin/plugins');

export const adminTogglePlugin = (name, enabled) =>
  request('POST', `/admin/plugins/${encodeURIComponent(name)}/toggle`, { enabled });

export const adminUploadPlugin = (file) => {
  const form = new FormData();
  form.append('file', file);
  return request('POST', '/admin/plugins/upload', form, true);
};

export const adminDeletePlugin = (name) =>
  request('DELETE', `/admin/plugins/${encodeURIComponent(name)}`);

// ── Fine-Tuning (Phase 5) ─────────────────────────────────────────────────────
export const adminListFinetuneSessions = () =>
  request('GET', '/admin/finetune/sessions');

export const adminCurateDataset = (sessionIds, format = 'alpaca', censorWords = null) =>
  request('POST', '/admin/finetune/curate', { session_ids: sessionIds, format, censor_words: censorWords });

export const adminCreateCustomModel = (name, baseModel, systemPrompt, temperature = 0.7) =>
  request('POST', '/admin/finetune/create-model', { name, base_model: baseModel, system_prompt: systemPrompt, temperature });


// ── Auth (Phase 5) ────────────────────────────────────────────────────────────
export const authRegister = (username, password, email = '', displayName = '') =>
  request('POST', '/auth/register', { username, password, email, display_name: displayName });

export const authLogin = (username, password) =>
  request('POST', '/auth/login', { username, password });

export const authMe = () =>
  request('GET', '/auth/me');

export const authLogout = () =>
  request('POST', '/auth/logout');


// ── Conversations (Phase 5) ───────────────────────────────────────────────────
export const listConversations = (limit = 50) =>
  request('GET', `/conversations?limit=${limit}`);

export const getConversation = (sessionId) =>
  request('GET', `/conversations/${sessionId}`);

export const deleteConversation = (sessionId) =>
  request('DELETE', `/conversations/${sessionId}`);

export const searchConversations = (q, limit = 30) =>
  request('GET', `/conversations/search?q=${encodeURIComponent(q)}&limit=${limit}`);

export const exportConversation = (sessionId) =>
  request('GET', `/conversations/${sessionId}/export`);


// ── WebSocket Chat Factory (Phase 5) ─────────────────────────────────────────
export function createChatWebSocket(onMessage, onOpen, onClose, onError) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  let wsHost = window.location.host;
  if (
    wsHost.includes('localhost:3000') ||
    wsHost.includes('127.0.0.1:3000') ||
    wsHost.includes('localhost:5173') ||
    wsHost.includes('127.0.0.1:5173') ||
    wsHost.includes('localhost:3001') ||
    wsHost.includes('127.0.0.1:3001')
  ) {
    wsHost = 'localhost:8000';
  }
  const wsBase = `${protocol}//${wsHost}/api`;
  const token = getToken();
  const url = token
    ? `${wsBase}/ws/chat?token=${token}`
    : `${wsBase}/ws/chat`;

  const ws = new WebSocket(url);
  ws.onopen    = onOpen  || (() => {});
  ws.onclose   = onClose || (() => {});
  ws.onerror   = onError || (() => {});
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onMessage(data);
    } catch { /* ignore malformed frames */ }
  };
  return ws;
}

// ── Skills Marketplace (Phase B) ─────────────────────────────────────────────
export const getSkills = () => request('GET', '/skills');
export const getSkill = (skillId) => request('GET', `/skills/${skillId}`);
export const saveSkill = (data) => request('POST', '/skills', data);
export const deleteSkill = (skillId) => request('DELETE', `/skills/${skillId}`);
export const activateSkill = (sessionId, skillId) =>
  request('POST', '/skills/activate', { session_id: sessionId, skill_id: skillId });

// ── Voice Profiles & Biometrics (Phase B) ──────────────────────────────────────
export const getVoiceProfiles = () => request('GET', '/voice/profiles');
export const enrollVoiceProfile = (profileName, userId, audioBlobs) => {
  const form = new FormData();
  form.append('profile_name', profileName);
  form.append('user_id', userId);
  audioBlobs.forEach((blob, i) => {
    form.append('audio_files', blob, `sample_${i}.wav`);
  });
  return request('POST', '/voice/enroll', form, true);
};
export const deleteVoiceProfile = (id) => request('DELETE', `/voice/profiles/${id}`);
export const getLockoutStatus = () => request('GET', '/voice/lockout-status');
export const getVoiceAttempts = (limit = 50, offset = 0) =>
  request('GET', `/voice/attempts?limit=${limit}&offset=${offset}`);
export const getVoiceMetrics = () => request('GET', '/voice/metrics');
export const getVoiceSecurityMetrics = () => request('GET', '/voice/security/metrics');
export const triggerVoiceCleanup = () => request('POST', '/voice/admin/cleanup');

// ── VS Code Extension Integration (Phase B) ───────────────────────────────────
export const getVSCodeStatus = (sessionId = '') =>
  request('GET', `/vscode/status${sessionId ? `?session_id=${sessionId}` : ''}`);
export const updateVSCodeContext = (activeFile, cursorLine, activeSymbol) =>
  request('POST', '/vscode/status/context', { active_file: activeFile, cursor_line: cursorLine, active_symbol: activeSymbol });
export const getVSCodeContext = () => request('GET', '/vscode/status/context');
export const executeVSCodeCommand = (command, params, sessionId = '') =>
  request('POST', '/vscode/execute', { command, params, session_id: sessionId });
export const scanWorkspaceCodebase = () => request('POST', '/vscode/index/scan');
export const queryWorkspaceSymbols = (q) => request('GET', `/vscode/index/query?q=${encodeURIComponent(q)}`);

// ── Automation (Phase B) ──────────────────────────────────────────────────────
export const createCommand = (deviceId, tool, params, rawInput = '') =>
  request('POST', '/v1/commands/create', {
    device_id: deviceId,
    tool,
    params,
    device_type: 'desktop',
    priority: 3,
    raw_input: rawInput,
    source_language: 'en',
    source: 'chat'
  });
export const getCommandsList = (limit = 100) => request('GET', '/v1/commands/?limit=' + limit);
export const getLiveActivity = (limit = 50) => request('GET', '/v1/commands/activity?limit=' + limit);
export const getDevicesList = () => request('GET', '/v1/devices/list');
export const getSystemHealth = () => request('GET', '/v1/admin/system/health');
export const getDashboardMetrics = () => request('GET', '/v1/admin/dashboard/metrics');

