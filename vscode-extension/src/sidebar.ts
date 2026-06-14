import * as vscode from 'vscode';

export class RudranSidebarProvider implements vscode.WebviewViewProvider {
    private _view?: vscode.WebviewView;
    public onMessageSent?: (msg: string) => void;
    public onCustomMessageReceived?: (data: any) => void;
    private _gatewayOnline: boolean = false;
    private _deviceId: string = '';

    constructor(private readonly _extensionUri: vscode.Uri) {}

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken
    ) {
        this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this._extensionUri]
        };

        webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

        // Receive messages from Webview JS and relay them back to main extension
        webviewView.webview.onDidReceiveMessage((data) => {
            if (this.onCustomMessageReceived) {
                this.onCustomMessageReceived(data);
            }
            switch (data.type) {
                case 'sendMessage':
                    if (this.onMessageSent) {
                        this.onMessageSent(data.value);
                    }
                    break;
                case 'showInfo':
                    vscode.window.showInformationMessage(data.value);
                    break;
                case 'showWarning':
                    vscode.window.showWarningMessage(data.value);
                    break;
            }
        });

        // Sync initial state
        this.updateWebviewState();
    }

    public setGatewayStatus(online: boolean) {
        this._gatewayOnline = online;
        this.updateWebviewState();
    }

    public setDeviceId(deviceId: string) {
        this._deviceId = deviceId;
        this.updateWebviewState();
    }

    private updateWebviewState() {
        if (this._view) {
            this._view.webview.postMessage({
                type: 'status',
                online: this._gatewayOnline,
                deviceId: this._deviceId,
                workspace: vscode.workspace.name || 'No Folder Open'
            });
            const editor = vscode.window.activeTextEditor;
            const hasSelection = editor ? !editor.selection.isEmpty : false;
            this._view.webview.postMessage({
                type: 'selection',
                hasSelection: hasSelection
            });
        }
    }

    /**
     * Send incoming chat stream chunks to the webview
     */
    public postMessageToWebview(message: any) {
        if (this._view) {
            this._view.webview.postMessage(message);
        }
    }

    private _getHtmlForWebview(webview: vscode.Webview): string {
        // Local path to css and js styles
        const scriptUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'media', 'sidebar.js'));
        const styleUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'media', 'sidebar.css'));

        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rudran AI Sidebar</title>
    <link href="${styleUri}" rel="stylesheet">
</head>
<body>
    <div class="header">
        <div class="logo">Rudran AI Assistant</div>
        <div id="status-badge" class="badge offline">Offline</div>
    </div>
    
    <!-- Tab Controls -->
    <div class="tabs">
        <button class="tab-btn active" onclick="openTab(event, 'tab-chat')">Chat</button>
        <button class="tab-btn" onclick="openTab(event, 'tab-projects')">Projects</button>
        <button class="tab-btn" onclick="openTab(event, 'tab-memory')">Memory</button>
        <button class="tab-btn" onclick="openTab(event, 'tab-tasks')">Tasks</button>
        <button class="tab-btn" onclick="openTab(event, 'tab-logs')">Logs</button>
    </div>

    <!-- Tab Contents -->
    <div id="tab-chat" class="tab-content active">
        <div id="chat-messages" class="messages-container">
            <div class="message assistant">வணக்கம்! நான் ருத்ரன் AI. நான் உங்களது VS Code workspace-ஐ நேரடியாகக் கையாள முடியும்.</div>
        </div>
        <div class="quick-actions" id="quick-actions-bar">
            <button class="action-btn" id="btn-explain" disabled title="Select code in editor to enable">விளக்கு (Explain)</button>
            <button class="action-btn" id="btn-test" disabled title="Select code in editor to enable">தேர்வு (Test)</button>
            <button class="action-btn" id="btn-fix" disabled title="Select code in editor to enable">திருத்து (Fix)</button>
            <button class="action-btn" id="btn-scan" title="Scan codebase index">ஸ்கேன் (Scan)</button>
        </div>
        <div class="input-container">
            <textarea id="chat-input" placeholder="Type a message (Tamil/English)..." rows="2"></textarea>
            <button id="send-btn">Send</button>
        </div>
    </div>

    <div id="tab-projects" class="tab-content">
        <div class="info-card">
            <h3>Active Project Context</h3>
            <div class="meta-row"><strong>Folder:</strong> <span id="proj-folder">No Folder Open</span></div>
            <div class="meta-row"><strong>Framework:</strong> <span class="tag">FastAPI</span></div>
            <div class="meta-row"><strong>Frontend:</strong> <span class="tag">React</span></div>
            <div class="meta-row"><strong>Database:</strong> <span class="tag">SQLite</span></div>
        </div>
    </div>

    <div id="tab-memory" class="tab-content">
        <div class="info-card">
            <h3>User & Session Memory</h3>
            <div class="meta-row"><strong>Device ID:</strong> <span id="dev-id" class="code-font">Not Registered</span></div>
            <p>Active preferences and facts collected by Rudran RAG system will sync here.</p>
        </div>
    </div>

    <div id="tab-tasks" class="tab-content">
        <div class="info-card">
            <h3>Pending & Active Tasks</h3>
            <ul class="task-list">
                <li class="task-item"><span class="bullet">•</span> Syncing workspace index...</li>
            </ul>
        </div>
    </div>

    <div id="tab-logs" class="tab-content">
        <div class="logs-container" id="logs-feed">
            <div class="log-line">[system] VS Code Sidebar Chat initialized.</div>
        </div>
    </div>

    <script src="${scriptUri}"></script>
</body>
</html>`;
    }
}
