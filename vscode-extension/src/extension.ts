import * as vscode from 'vscode';
import { RudranSidebarProvider } from './sidebar';

let wsClient: any = null;
let heartbeatInterval: NodeJS.Timeout | null = null;
let reconnectTimeout: NodeJS.Timeout | null = null;

export function activate(context: vscode.ExtensionContext) {
    console.log('Rudran AI Extension is active.');

    // 1. Initialize Sidebar Chat Provider
    const sidebarProvider = new RudranSidebarProvider(context.extensionUri);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider(
            'rudran-ai-chat-sidebar',
            sidebarProvider
        )
    );

    // 2. Establish Connection to WebSocket Gateway
    const session_id = vscode.env.sessionId;
    connectToGateway(session_id, sidebarProvider);

    // 3. Register custom message handler for coding quick actions
    sidebarProvider.onCustomMessageReceived = async (data: any) => {
        const editor = vscode.window.activeTextEditor;
        const selection = editor ? editor.document.getText(editor.selection) : '';

        if (data.type === 'explainCode' || data.type === 'generateTests' || data.type === 'fixBugs') {
            if (!selection) {
                vscode.window.showWarningMessage('பிழை: தயவுசெய்து குறியீட்டைத் தேர்ந்தெடுத்து முயற்சிக்கவும்!');
                sidebarProvider.postMessageToWebview({
                    type: 'chat_error',
                    message: 'No code selected in active editor.'
                });
                return;
            }

            let prompt = '';
            if (data.type === 'explainCode') {
                prompt = `விளக்கவும் (Explain selected code in Tamil):\n\n\`\`\`\n${selection}\n\`\`\``;
            } else if (data.type === 'generateTests') {
                prompt = `இந்தக் குறியீட்டிற்கு தேர்வுகள் எழுதுக (Write unit tests in Tamil for this code):\n\n\`\`\`\n${selection}\n\`\`\``;
            } else if (data.type === 'fixBugs') {
                prompt = `இந்தக் குறியீட்டில் உள்ள பிழைகளைத் திருத்துக (Find and fix bugs in this code):\n\n\`\`\`\n${selection}\n\`\`\``;
            }

            if (wsClient && wsClient.readyState === 1) {
                wsClient.send(JSON.stringify({
                    type: 'chat_message',
                    message: prompt,
                    session_id: session_id
                }));
            } else {
                vscode.window.showWarningMessage('Rudran AI: Gateway is offline. Message not sent.');
            }
        } else if (data.type === 'scanWorkspace') {
            const config = vscode.workspace.getConfiguration('rudran-ai');
            const gatewayUrl = config.get<string>('gatewayUrl') || 'ws://localhost:8000/api/ws/vscode';
            try {
                const res = await triggerWorkspaceScan(gatewayUrl);
                sidebarProvider.postMessageToWebview({
                    type: 'scan_completed',
                    files: res.files_scanned || 0,
                    classes: res.classes || 0,
                    functions: res.functions || 0,
                    routes: res.routes || 0
                });
            } catch (err: any) {
                vscode.window.showErrorMessage('Rudran AI: Workspace scan failed: ' + err.message);
                sidebarProvider.postMessageToWebview({
                    type: 'chat_error',
                    message: 'Scan failed: ' + err.message
                });
            }
        }
    };

    // 4. Register selection change listeners
    context.subscriptions.push(
        vscode.window.onDidChangeTextEditorSelection(async (event) => {
            const hasSelection = !event.selections[0].isEmpty;
            sidebarProvider.postMessageToWebview({
                type: 'selection',
                hasSelection: hasSelection
            });

            const editor = event.textEditor;
            if (editor) {
                const relPath = getRelativePath(editor.document);
                const cursorLine = editor.selection.active.line + 1;
                const activeSymbol = await getActiveSymbol(editor.document, editor.selection.active);
                try {
                    await syncContextToBackend(relPath, cursorLine, activeSymbol);
                } catch (e) {
                    console.error('Error syncing context on selection change:', e);
                }
            }
        })
    );

    context.subscriptions.push(
        vscode.window.onDidChangeActiveTextEditor(async (editor) => {
            const hasSelection = editor ? !editor.selection.isEmpty : false;
            sidebarProvider.postMessageToWebview({
                type: 'selection',
                hasSelection: hasSelection
            });

            if (editor) {
                const relPath = getRelativePath(editor.document);
                const cursorLine = editor.selection.active.line + 1;
                const activeSymbol = await getActiveSymbol(editor.document, editor.selection.active);
                try {
                    await syncContextToBackend(relPath, cursorLine, activeSymbol);
                } catch (e) {
                    console.error('Error syncing context on active editor change:', e);
                }
            } else {
                try {
                    await syncContextToBackend('', 0, '');
                } catch (e) {
                    console.error('Error syncing context on editor close:', e);
                }
            }
        })
    );

    // Register focus command
    context.subscriptions.push(
        vscode.commands.registerCommand('rudran-ai-vscode.focus', () => {
            vscode.commands.executeCommand('workbench.view.extension.rudran-ai-sidebar');
        })
    );
}

function connectToGateway(sessionId: string, sidebarProvider: RudranSidebarProvider) {
    // Dynamic URL detection - uses configuration setting or local fallback
    const config = vscode.workspace.getConfiguration('rudran-ai');
    const gatewayUrl = config.get<string>('gatewayUrl') || 'ws://localhost:8000/api/ws/vscode';
    
    // We import ws dynamically or mock it in extension runtime if WebSocket API is built-in
    // In VS Code extension node environments, we typically require('ws')
    try {
        const WebSocketClass = require('ws');
        wsClient = new WebSocketClass(gatewayUrl);
    } catch (e) {
        console.error('WebSocket module not found, using global WebSocket if available', e);
        // Fallback for custom runtimes / browser-based code-server instances
        if (typeof WebSocket !== 'undefined') {
            wsClient = new WebSocket(gatewayUrl);
        } else {
            vscode.window.showErrorMessage('Rudran AI: Failed to load WebSocket client.');
            return;
        }
    }

    wsClient.on('open', () => {
        console.log('Connected to Rudran AI WebSocket Gateway.');
        sidebarProvider.setGatewayStatus(true);
        
        // Register extension device capabilities
        const registration = {
            type: 'register',
            user_id: 'admin-user-123',
            session_id: sessionId,
            device_name: 'VS Code Workspace',
            capabilities: [
                'vscode.open_file',
                'vscode.search_code',
                'vscode.run_tests',
                'vscode.create_project'
            ]
        };
        wsClient.send(JSON.stringify(registration));
        
        // Start Heartbeat interval (every 10 seconds)
        if (heartbeatInterval) { clearInterval(heartbeatInterval); }
        heartbeatInterval = setInterval(() => {
            if (wsClient && wsClient.readyState === 1) {
                wsClient.send(JSON.stringify({
                    type: 'heartbeat',
                    agent_version: '1.0.0',
                    system_info: {
                        vscode_version: vscode.version,
                        workspace_name: vscode.workspace.name || 'No Folder Opened'
                    }
                }));
            }
        }, 10000);
    });

    wsClient.on('message', async (data: string) => {
        try {
            const payload = JSON.parse(data);
            
            // Handle RPC commands delegated by the agent orchestrator
            if (payload.type === 'command') {
                const result = await handleVSCodeCommand(payload.command, payload.params);
                // Send response back
                wsClient.send(JSON.stringify({
                    type: 'response',
                    id: payload.id,
                    result: result
                }));
            } else if (payload.type === 'register_response') {
                console.log('Registration response:', payload);
                sidebarProvider.setDeviceId(payload.device_id);
            }
        } catch (err) {
            console.error('Failed to parse incoming WebSocket message:', err);
        }
    });

    wsClient.on('close', () => {
        console.warn('Connection closed. Retrying reconnect...');
        sidebarProvider.setGatewayStatus(false);
        if (heartbeatInterval) { clearInterval(heartbeatInterval); }
        
        // Trigger reconnect after 5 seconds
        if (reconnectTimeout) { clearTimeout(reconnectTimeout); }
        reconnectTimeout = setTimeout(() => {
            connectToGateway(sessionId, sidebarProvider);
        }, 5000);
    });

    wsClient.on('error', (err: any) => {
        console.error('WebSocket connection error:', err);
    });

    // Link Sidebar Provider sending to WebSocket
    sidebarProvider.onMessageSent = (msg: string) => {
        if (wsClient && wsClient.readyState === 1) {
            wsClient.send(JSON.stringify({
                type: 'chat_message',
                message: msg,
                session_id: sessionId
            }));
        } else {
            vscode.window.showWarningMessage('Rudran AI: Gateway is offline. Message not sent.');
        }
    };
}

async function handleVSCodeCommand(command: string, params: any): Promise<any> {
    console.log(`Executing delegated VS Code command: ${command} with params:`, params);
    
    switch (command) {
        case 'vscode.open_file': {
            const filePath = params.file_path;
            if (!filePath) { return { status: 'error', message: 'Missing file_path parameter' }; }
            try {
                const uri = vscode.Uri.file(filePath);
                const doc = await vscode.workspace.openTextDocument(uri);
                const editor = await vscode.window.showTextDocument(doc);
                
                // Optional: Scroll to specific line range
                const startLine = params.start_line;
                const endLine = params.end_line;
                if (typeof startLine === 'number') {
                    const range = new vscode.Range(
                        new vscode.Position(startLine - 1, 0),
                        new vscode.Position((endLine || startLine) - 1, 0)
                    );
                    editor.revealRange(range, vscode.TextEditorRevealType.InCenter);
                    editor.selection = new vscode.Selection(range.start, range.end);
                }
                return { status: 'success', file: filePath };
            } catch (err: any) {
                return { status: 'error', message: err.message };
            }
        }
        
        case 'vscode.search_code': {
            const query = params.query;
            if (!query) { return { status: 'error', message: 'Missing query parameter' }; }
            try {
                // Search workspace using vscode findFiles or text search commands
                // Return relative paths of top 10 matches
                const files = await vscode.workspace.findFiles(`**/*${query}*`, undefined, 10);
                const fileList = files.map(f => f.fsPath);
                return { status: 'success', matches: fileList };
            } catch (err: any) {
                return { status: 'error', message: err.message };
            }
        }
        
        case 'vscode.run_tests': {
            const testCommand = params.test_command || 'pytest';
            try {
                // Run tests inside VS Code terminal environment
                // Create a temporary task or terminal instance to display logs
                const terminal = vscode.window.createTerminal('Rudran AI Test Runner');
                terminal.show();
                terminal.sendText(testCommand);
                return { status: 'success', message: `Triggered '${testCommand}' in active VS Code terminal.` };
            } catch (err: any) {
                return { status: 'error', message: err.message };
            }
        }
        
        case 'vscode.create_project': {
            const projectName = params.project_name;
            if (!projectName) { return { status: 'error', message: 'Missing project_name parameter' }; }
            try {
                // Create folders relative to active workspace if opened, else temp/local directory
                const folders = vscode.workspace.workspaceFolders;
                if (folders && folders.length > 0) {
                    const rootUri = folders[0].uri;
                    const newProjectUri = vscode.Uri.joinPath(rootUri, projectName);
                    await vscode.workspace.fs.createDirectory(newProjectUri);
                    return { status: 'success', path: newProjectUri.fsPath };
                } else {
                    return { status: 'error', message: 'No active workspace folder open. Open a workspace folder first.' };
                }
            } catch (err: any) {
                return { status: 'error', message: err.message };
            }
        }
        
        default:
            return { status: 'error', message: `Unknown command: ${command}` };
    }
}

export function deactivate() {
    if (heartbeatInterval) { clearInterval(heartbeatInterval); }
    if (reconnectTimeout) { clearTimeout(reconnectTimeout); }
    if (wsClient) { wsClient.close(); }
}

function triggerWorkspaceScan(gatewayUrl: string): Promise<any> {
    return new Promise((resolve, reject) => {
        const urlStr = gatewayUrl.replace('/ws/vscode', '/vscode/index/scan').replace('ws://', 'http://').replace('wss://', 'https://');
        const url = new URL(urlStr);
        const httpLib = url.protocol === 'https:' ? require('https') : require('http');
        
        const req = httpLib.request({
            hostname: url.hostname,
            port: url.port || (url.protocol === 'https:' ? 443 : 80),
            path: url.pathname,
            method: 'POST',
            headers: {
                'Content-Length': '0'
            }
        }, (res: any) => {
            let body = '';
            res.on('data', (chunk: any) => body += chunk);
            res.on('end', () => {
                try {
                    resolve(JSON.parse(body));
                } catch (e) {
                    resolve({ status: 'success', detail: body });
                }
            });
        });
        
        req.on('error', (err: any) => reject(err));
        req.end();
    });
}

function getRelativePath(document: vscode.TextDocument): string {
    let relPath = document.uri.fsPath;
    const folders = vscode.workspace.workspaceFolders;
    if (folders && folders.length > 0) {
        const rootPath = folders[0].uri.fsPath;
        if (relPath.startsWith(rootPath)) {
            relPath = relPath.substring(rootPath.length).replace(/\\/g, '/');
            if (relPath.startsWith('/')) { relPath = relPath.substring(1); }
        }
    }
    return relPath;
}

async function getActiveSymbol(document: vscode.TextDocument, position: vscode.Position): Promise<string> {
    try {
        const symbols = await vscode.commands.executeCommand<vscode.DocumentSymbol[]>(
            'vscode.executeDocumentSymbolProvider',
            document.uri
        );
        if (!symbols) { return ''; }
        
        let currentSymbol = '';
        function traverse(syms: vscode.DocumentSymbol[]) {
            for (const sym of syms) {
                if (sym.range.contains(position)) {
                    currentSymbol = sym.name;
                    if (sym.children && sym.children.length > 0) {
                        traverse(sym.children);
                    }
                }
            }
        }
        traverse(symbols);
        return currentSymbol;
    } catch (e) {
        console.error('Error fetching document symbols:', e);
        return '';
    }
}

async function syncContextToBackend(activeFile: string, cursorLine: number, activeSymbol: string): Promise<any> {
    const config = vscode.workspace.getConfiguration('rudran-ai');
    const gatewayUrl = config.get<string>('gatewayUrl') || 'ws://localhost:8000/api/ws/vscode';
    
    const urlStr = gatewayUrl
        .replace('/ws/vscode', '/vscode/status/context')
        .replace('ws://', 'http://')
        .replace('wss://', 'https://');
        
    const url = new URL(urlStr);
    const httpLib = url.protocol === 'https:' ? require('https') : require('http');
    
    const payload = JSON.stringify({
        active_file: activeFile,
        cursor_line: cursorLine,
        active_symbol: activeSymbol
    });
    
    return new Promise((resolve, reject) => {
        const req = httpLib.request({
            hostname: url.hostname,
            port: url.port || (url.protocol === 'https:' ? 443 : 80),
            path: url.pathname,
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(payload)
            }
        }, (res: any) => {
            let body = '';
            res.on('data', (chunk: any) => body += chunk);
            res.on('end', () => {
                try {
                    resolve(JSON.parse(body));
                } catch (e) {
                    resolve(body);
                }
            });
        });
        
        req.on('error', (err: any) => reject(err));
        req.write(payload);
        req.end();
    });
}

