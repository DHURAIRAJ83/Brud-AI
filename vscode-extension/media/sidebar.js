// Acquire VS Code API (available in webview panel runtime)
const vscode = acquireVsCodeApi();

// DOM elements
const statusBadge = document.getElementById('status-badge');
const chatMessages = document.getElementById('chat-messages');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const projFolder = document.getElementById('proj-folder');
const devIdSpan = document.getElementById('dev-id');
const logsFeed = document.getElementById('logs-feed');
const btnExplain = document.getElementById('btn-explain');
const btnTest = document.getElementById('btn-test');
const btnFix = document.getElementById('btn-fix');
const btnScan = document.getElementById('btn-scan');

let currentAssistantBubble = null;

// Tab switcher logic
function openTab(evt, tabName) {
    const tabContents = document.getElementsByClassName("tab-content");
    for (let i = 0; i < tabContents.length; i++) {
        tabContents[i].classList.remove("active");
    }

    const tabButtons = document.getElementsByClassName("tab-btn");
    for (let i = 0; i < tabButtons.length; i++) {
        tabButtons[i].classList.remove("active");
    }

    document.getElementById(tabName).classList.add("active");
    evt.currentTarget.classList.add("active");
    
    appendLog(`[sidebar] Switched to tab: ${tabName}`);
}

// Send Message logic
function sendMessage() {
    const text = chatInput.value.trim();
    if (!text) return;

    // Append user message bubble
    appendMessage('user', text);
    
    // Clear input
    chatInput.value = '';
    
    // Create new assistant container for incoming stream
    currentAssistantBubble = appendMessage('assistant', '...');

    // Post to extension host
    vscode.postMessage({
        type: 'sendMessage',
        value: text
    });
    
    appendLog(`[chat] User: ${text}`);
}

// Event Listeners
sendBtn.addEventListener('click', sendMessage);
chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

btnExplain.addEventListener('click', () => {
    appendMessage('user', 'Explain selected code | இந்த குறியீட்டை விளக்கவும்');
    currentAssistantBubble = appendMessage('assistant', '...');
    vscode.postMessage({ type: 'explainCode' });
});

btnTest.addEventListener('click', () => {
    appendMessage('user', 'Write unit tests for selected code | இந்த குறியீட்டிற்கு தேர்வுகள் எழுதுக');
    currentAssistantBubble = appendMessage('assistant', '...');
    vscode.postMessage({ type: 'generateTests' });
});

btnFix.addEventListener('click', () => {
    appendMessage('user', 'Find and fix bugs in selected code | இந்த குறியீட்டில் உள்ள பிழைகளை திருத்துக');
    currentAssistantBubble = appendMessage('assistant', '...');
    vscode.postMessage({ type: 'fixBugs' });
});

btnScan.addEventListener('click', () => {
    appendMessage('user', 'Scan codebase index | குறியீட்டு கட்டமைப்பை ஸ்கேன் செய்க');
    currentAssistantBubble = appendMessage('assistant', 'Scanning...');
    vscode.postMessage({ type: 'scanWorkspace' });
});

// Listen for messages from extension host (src/sidebar.ts)
window.addEventListener('message', event => {
    const message = event.data;
    
    switch (message.type) {
        case 'status':
            // Update gateway online badge
            if (message.online) {
                statusBadge.textContent = 'Online';
                statusBadge.className = 'badge online';
            } else {
                statusBadge.textContent = 'Offline';
                statusBadge.className = 'badge offline';
            }
            
            // Update workspace folder
            if (projFolder) {
                projFolder.textContent = message.workspace;
            }
            
            // Update device id
            if (devIdSpan) {
                devIdSpan.textContent = message.deviceId || 'Not Registered';
            }
            
            appendLog(`[status] State sync: connected=${message.online}, device_id=${message.deviceId}`);
            break;

        case 'selection':
            const hasSel = message.hasSelection;
            btnExplain.disabled = !hasSel;
            btnTest.disabled = !hasSel;
            btnFix.disabled = !hasSel;
            
            const hint = hasSel ? 'Click to process selected code' : 'Select code in editor to enable';
            btnExplain.title = hint;
            btnTest.title = hint;
            btnFix.title = hint;
            break;

        case 'scan_completed':
            if (currentAssistantBubble && currentAssistantBubble.textContent === 'Scanning...') {
                currentAssistantBubble.textContent = `Scan completed. Scanned ${message.files} files, ${message.classes} classes, ${message.functions} functions, ${message.routes} routes.`;
            }
            appendLog(`[indexer] Scan complete: ${message.files} files`);
            break;
            
        case 'chat_token':
            // Handle token-by-token streaming
            const data = message.data;
            if (data.type === 'meta') {
                appendLog(`[llama] Model selected: ${data.model}, Intent detected: ${data.intent}`);
            } else if (data.type === 'token') {
                if (currentAssistantBubble) {
                    if (currentAssistantBubble.textContent === '...') {
                        currentAssistantBubble.textContent = '';
                    }
                    currentAssistantBubble.textContent += data.token;
                    
                    // Auto-scroll
                    chatMessages.scrollTop = chatMessages.scrollHeight;
                }
            }
            break;
            
        case 'chat_error':
            if (currentAssistantBubble) {
                currentAssistantBubble.textContent = `Error: ${message.message}`;
                currentAssistantBubble.style.color = 'var(--danger)';
            }
            appendLog(`[error] Chat failure: ${message.message}`);
            break;
    }
});

function appendMessage(role, text) {
    const bubble = document.createElement('div');
    bubble.className = `message ${role}`;
    bubble.textContent = text;
    chatMessages.appendChild(bubble);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return bubble;
}

function appendLog(line) {
    if (logsFeed) {
        const time = new Date().toLocaleTimeString();
        const lineDiv = document.createElement('div');
        lineDiv.className = 'log-line';
        lineDiv.textContent = `[${time}] ${line}`;
        logsFeed.appendChild(lineDiv);
        logsFeed.scrollTop = logsFeed.scrollHeight;
    }
}
