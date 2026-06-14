/**
 * Tamil AI Assistant — Electron Main Process v4
 * Phase 4: Hybrid AI Runtime
 *
 * On startup:
 *   1. Check localhost:11434 (local Ollama)
 *   2. If unavailable → show 5-page setup wizard
 *   3. Start FastAPI backend
 *   4. Load React frontend
 */

const { app, BrowserWindow, shell, ipcMain, Menu, globalShortcut, Tray, Notification } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');

let mainWindow    = null;
let splashWindow  = null;
let backendProcess = null;

const BACKEND_PORT  = 8000;
const FRONTEND_PORT = 3000;
const BACKEND_URL   = `http://localhost:${BACKEND_PORT}`;
const FRONTEND_URL  = `http://localhost:${FRONTEND_PORT}`;
const OLLAMA_URL    = 'http://localhost:11434';

// ── Utility: HTTP GET probe ───────────────────────────────────────────────────
function probe(url) {
  return new Promise((resolve) => {
    http.get(url, (res) => resolve(res.statusCode < 500))
      .on('error', () => resolve(false))
      .setTimeout(3000, function () { this.destroy(); resolve(false); });
  });
}

// ── Backend startup ───────────────────────────────────────────────────────────
function startBackend() {
  const backendDir = path.join(__dirname, '..', 'backend');
  const pythonPath = process.platform === 'win32'
    ? path.join(backendDir, 'venv', 'Scripts', 'python.exe')
    : path.join(backendDir, 'venv', 'bin', 'python');

  console.log('[Desktop] Starting FastAPI backend…');
  backendProcess = spawn(pythonPath, ['main.py'], {
    cwd: backendDir,
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  backendProcess.stdout.on('data', (d) => console.log('[Backend]', d.toString().trim()));
  backendProcess.stderr.on('data', (d) => console.error('[Backend ERR]', d.toString().trim()));
  backendProcess.on('close', (code) => console.log(`[Backend] exited with code ${code}`));
}

// ── Wait for backend to be ready ──────────────────────────────────────────────
function waitForBackend(retries = 20, delay = 1000) {
  return new Promise((resolve, reject) => {
    const attempt = (remaining) => {
      http.get(`${BACKEND_URL}/health`, (res) => {
        if (res.statusCode === 200) resolve();
        else if (remaining > 0) setTimeout(() => attempt(remaining - 1), delay);
        else reject(new Error('Backend did not start in time'));
      }).on('error', () => {
        if (remaining > 0) setTimeout(() => attempt(remaining - 1), delay);
        else reject(new Error('Backend not reachable'));
      });
    };
    attempt(retries);
  });
}

// ── Create main window ────────────────────────────────────────────────────────
function createWindow(url) {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    title: 'Tamil AI Assistant',
    backgroundColor: '#0a0a14',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
  });

  mainWindow.loadURL(url);

  mainWindow.webContents.setWindowOpenHandler(({ url: u }) => {
    shell.openExternal(u);
    return { action: 'deny' };
  });

  mainWindow.on('close', (event) => {
    if (!app.isQuitting) {
      event.preventDefault();
      mainWindow.hide();
    }
  });

  mainWindow.on('closed', () => { mainWindow = null; });
}

// ── Splash screen HTML ────────────────────────────────────────────────────────
function splashHTML(message, sub = '') {
  return `data:text/html,<!DOCTYPE html>
<html style="background:#0a0a14;color:#c4b5fd;font-family:'Segoe UI',sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;flex-direction:column;gap:16px;margin:0;">
<div style="font-size:52px;animation:pulse 2s ease-in-out infinite;">🤖</div>
<div style="font-size:22px;font-weight:800;color:#fff;">Tamil AI Assistant</div>
<div style="font-size:15px;color:#a78bfa;">${message}</div>
${sub ? `<div style="font-size:12px;color:#6b7280;margin-top:4px;">${sub}</div>` : ''}
<style>@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.5}}</style>
</html>`;
}

// ── Setup Wizard HTML (5 pages) ───────────────────────────────────────────────
function wizardHTML() {
  return `data:text/html,<!DOCTYPE html>
<html style="background:#0a0a14;color:#fff;font-family:'Segoe UI',sans-serif;margin:0;height:100vh;overflow:hidden;">
<head>
<style>
  *{box-sizing:border-box}
  body{margin:0;display:flex;align-items:center;justify-content:center;height:100vh;background:linear-gradient(135deg,#0a0a14 0%,#12121e 100%)}
  .wizard{width:480px;padding:2.5rem;background:#12121e;border:1px solid rgba(167,139,250,0.2);border-radius:20px;box-shadow:0 24px 64px rgba(0,0,0,0.6)}
  .step{display:none;flex-direction:column;gap:1rem;animation:fadeIn 0.25s ease}
  .step.active{display:flex}
  @keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
  h2{font-size:1.4rem;font-weight:800;margin:0;text-align:center}
  p{color:rgba(255,255,255,0.55);font-size:0.875rem;line-height:1.6;text-align:center;margin:0}
  .icon{font-size:52px;text-align:center}
  .btn{width:100%;padding:0.875rem;border-radius:10px;border:none;font-size:0.9rem;font-weight:700;cursor:pointer;font-family:inherit;transition:all 0.2s}
  .btn-primary{background:linear-gradient(135deg,#7c5cfc,#a78bfa);color:#fff}
  .btn-primary:hover{transform:translateY(-1px);box-shadow:0 4px 16px rgba(124,92,252,0.4)}
  .btn-secondary{background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.1);color:rgba(255,255,255,0.6)}
  .btn-secondary:hover{background:rgba(255,255,255,0.1)}
  .btn-green{background:linear-gradient(135deg,#22d3a5,#0ea5e9);color:#fff}
  .btn-green:hover{transform:translateY(-1px)}
  .btn-blue{background:rgba(96,165,250,0.15);border:1px solid rgba(96,165,250,0.3);color:#93c5fd}
  .btn-blue:hover{background:rgba(96,165,250,0.25)}
  .progress{display:flex;gap:6px;justify-content:center;margin-bottom:0.5rem}
  .dot{width:8px;height:8px;border-radius:50%;background:rgba(255,255,255,0.15);transition:all 0.3s}
  .dot.active{background:#a78bfa;transform:scale(1.3)}
  .dot.done{background:rgba(124,92,252,0.5)}
  .consent-box{background:rgba(96,165,250,0.06);border:1px solid rgba(96,165,250,0.2);border-radius:10px;padding:1rem;font-size:0.82rem;color:rgba(255,255,255,0.65);line-height:1.7}
  .consent-box strong{color:#93c5fd}
  ul{margin:0.4rem 0 0;padding-left:1.2rem}
  .finish-list{list-style:none;padding:0;display:flex;flex-direction:column;gap:0.4rem}
  .finish-list li{display:flex;align-items:center;gap:0.5rem;font-size:0.85rem;color:rgba(255,255,255,0.65)}
</style>
</head>
<body>
<div class="wizard">
  <div class="progress" id="progress">
    <div class="dot active" id="d0"></div>
    <div class="dot" id="d1"></div>
    <div class="dot" id="d2"></div>
    <div class="dot" id="d3"></div>
    <div class="dot" id="d4"></div>
  </div>

  <!-- Page 1: Welcome -->
  <div class="step active" id="step-0">
    <div class="icon">🤖</div>
    <h2>Welcome to Tamil AI</h2>
    <p>Your intelligent assistant for <strong style="color:#a78bfa">Tamil</strong>, English, and Tanglish.<br>Let's get you set up in under a minute.</p>
    <button class="btn btn-primary" onclick="goto(1)">Get Started →</button>
  </div>

  <!-- Page 2: Local AI Setup -->
  <div class="step" id="step-1">
    <div class="icon">🖥️</div>
    <h2>Local AI Setup</h2>
    <p>Tamil AI works best with <strong style="color:#22d3a5">Ollama</strong> installed locally — fully private, offline-capable AI on your own computer.</p>
    <button class="btn btn-green" onclick="installOllama()">⬇️ Install Ollama (Free)</button>
    <button class="btn btn-secondary" onclick="goto(2)">I already have Ollama →</button>
  </div>

  <!-- Page 3: Online AI Option -->
  <div class="step" id="step-2">
    <div class="icon">☁️</div>
    <h2>Online AI Option</h2>
    <p>No local Ollama? No problem. Tamil AI can securely route your queries to our <strong style="color:#60a5fa">cloud AI server</strong> instead.</p>
    <button class="btn btn-blue" onclick="goto(3)">☁️ Use Online AI →</button>
    <button class="btn btn-secondary" onclick="goto(3)">Skip for now →</button>
  </div>

  <!-- Page 4: Consent -->
  <div class="step" id="step-3">
    <div class="icon">🔒</div>
    <h2>Privacy Consent</h2>
    <div class="consent-box">
      <strong>Your messages will be securely processed by our VPS AI server.</strong>
      <ul>
        <li>Encrypted in transit (HTTPS)</li>
        <li>Not stored or used for AI training</li>
        <li>You can switch to Local AI at any time</li>
      </ul>
    </div>
    <button class="btn btn-blue" onclick="acceptCloud()">✅ Accept &amp; Continue</button>
    <button class="btn btn-secondary" onclick="goto(2)">← Go Back</button>
  </div>

  <!-- Page 5: Finish -->
  <div class="step" id="step-4">
    <div class="icon">🎉</div>
    <h2>You're All Set!</h2>
    <p>Tamil AI is ready to assist you.</p>
    <ul class="finish-list">
      <li>✅ Hybrid mode enabled — auto-switches Local ↔ Cloud</li>
      <li>✅ Smart model routing active</li>
      <li>✅ Tamil · English · Tanglish supported</li>
      <li>✅ Voice STT + streaming enabled</li>
    </ul>
    <button class="btn btn-primary" onclick="finish()">🚀 Open Tamil AI</button>
  </div>
</div>
<script>
  let current = 0;
  function goto(n) {
    document.getElementById('step-' + current).classList.remove('active');
    document.getElementById('d' + current).classList.remove('active');
    document.getElementById('d' + current).classList.add('done');
    current = n;
    document.getElementById('step-' + current).classList.add('active');
    document.getElementById('d' + current).classList.add('active');
  }
  function installOllama() {
    // Open in real browser
    var a = document.createElement('a'); a.href='https://ollama.com/download'; a.target='_blank'; a.click();
    goto(2);
  }
  function acceptCloud() {
    localStorage.setItem('ai_mode', 'cloud');
    localStorage.setItem('cloud_consent', 'true');
    goto(4);
  }
  function finish() {
    // Signal Electron to proceed
    window.location.href = 'app://finish';
  }
</script>
</body>
</html>`;
}

let tray = null;

function createTray() {
  let trayIconPath = path.join(__dirname, 'assets', 'icon.png');
  try {
    const fs = require('fs');
    if (!fs.existsSync(trayIconPath)) {
      trayIconPath = path.join(__dirname, '..', 'landing', 'public', 'favicon.ico');
    }
    if (!fs.existsSync(trayIconPath)) {
      const { nativeImage } = require('electron');
      tray = new Tray(nativeImage.createEmpty());
    } else {
      tray = new Tray(trayIconPath);
    }
  } catch (err) {
    console.error('[Desktop] Failed to initialize tray icon, using empty tray', err);
    const { nativeImage } = require('electron');
    tray = new Tray(nativeImage.createEmpty());
  }

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'உதவியாளரைத் திற (Open Assistant)',
      click: () => {
        if (mainWindow) {
          mainWindow.show();
          mainWindow.focus();
        }
      }
    },
    {
      label: 'சேவை நிலை (Check Status)',
      click: async () => {
        const alive = await probe(`${BACKEND_URL}/health`);
        const statusMsg = alive ? 'FastAPI Backend is running | சேவை இயங்குகிறது' : 'FastAPI Backend is offline | சேவை நிறுத்தப்பட்டுள்ளது';
        if (Notification.isSupported()) {
          new Notification({
            title: 'Tamil AI Status',
            body: statusMsg,
            silent: false
          }).show();
        }
      }
    },
    { type: 'separator' },
    {
      label: 'வெளியேறு (Quit)',
      click: () => {
        app.isQuitting = true;
        app.quit();
      }
    }
  ]);

  tray.setToolTip('Tamil AI Assistant');
  tray.setContextMenu(contextMenu);

  tray.on('double-click', () => {
    if (mainWindow) {
      if (mainWindow.isVisible()) {
        mainWindow.hide();
      } else {
        mainWindow.show();
        mainWindow.focus();
      }
    }
  });
}

function registerHotkey() {
  globalShortcut.register('Ctrl+Alt+V', () => {
    if (mainWindow) {
      if (mainWindow.isFocused() && mainWindow.isVisible()) {
        mainWindow.hide();
      } else {
        mainWindow.show();
        mainWindow.focus();
      }
    }
  });
}

// ── App lifecycle ─────────────────────────────────────────────────────────────
app.whenReady().then(async () => {
  createTray();
  registerHotkey();
  Menu.setApplicationMenu(null);

  // IPC: handle finish signal from wizard
  ipcMain.on('wizard-finish', () => {
    if (splashWindow) { splashWindow.close(); splashWindow = null; }
    startBackend();
    launchApp();
  });

  // ── Step 1: Check local Ollama ──────────────────────────────────────────
  splashWindow = new BrowserWindow({
    width: 460, height: 340,
    backgroundColor: '#0a0a14',
    frame: false,
    resizable: false,
    webPreferences: { nodeIntegration: false, contextIsolation: true },
  });
  splashWindow.loadURL(splashHTML('Checking local AI…', 'Probing localhost:11434'));

  const ollamaAlive = await probe(OLLAMA_URL + '/api/tags');
  console.log('[Desktop] Ollama alive:', ollamaAlive);

  if (!ollamaAlive) {
    // ── Step 2: Show setup wizard ───────────────────────────────────────
    console.log('[Desktop] Ollama not found — showing setup wizard');
    splashWindow.setSize(520, 600);
    splashWindow.setResizable(false);
    splashWindow.center();
    splashWindow.loadURL(wizardHTML());

    // Listen for wizard finish via navigation to app://finish
    splashWindow.webContents.on('will-navigate', (event, url) => {
      if (url.startsWith('app://finish')) {
        event.preventDefault();
        splashWindow.close();
        splashWindow = null;
        startBackend();
        launchApp();
      }
    });
    return; // Wait for user to finish wizard
  }

  // ── Ollama found — proceed normally ──────────────────────────────────
  splashWindow.loadURL(splashHTML('Starting AI engine…', 'Initializing FastAPI backend'));
  startBackend();
  await launchApp();
});

async function launchApp() {
  // Update splash if still open
  if (splashWindow) {
    splashWindow.loadURL(splashHTML('Loading interface…', 'Almost ready'));
  }

  try {
    await waitForBackend();
    if (splashWindow) { splashWindow.close(); splashWindow = null; }
    createWindow(FRONTEND_URL);
    console.log('[Desktop] Tamil AI v4 ready!');
  } catch (err) {
    const errHTML = `data:text/html,<!DOCTYPE html>
<html style="background:#0a0a14;color:#ef4444;font-family:'Segoe UI',sans-serif;padding:40px;text-align:center;">
<h2 style="color:#ef4444">⚠️ Backend Failed to Start</h2>
<p style="color:#8888aa">${err.message}</p>
<p style="color:#6b7280;font-size:12px">Make sure Python venv is set up in the backend folder.</p>
</html>`;
    if (splashWindow) splashWindow.loadURL(errHTML);
    else {
      const errWin = new BrowserWindow({ width: 480, height: 300, backgroundColor: '#0a0a14' });
      errWin.loadURL(errHTML);
    }
  }
}

app.on('window-all-closed', () => {
  if (backendProcess) backendProcess.kill();
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  globalShortcut.unregisterAll();
  if (backendProcess) backendProcess.kill();
});
