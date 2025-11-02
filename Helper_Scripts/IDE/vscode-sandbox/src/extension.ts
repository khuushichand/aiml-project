import * as vscode from 'vscode';

export function activate(context: vscode.ExtensionContext) {
  const output = vscode.window.createOutputChannel('tldw Sandbox');

  const disposable = vscode.commands.registerCommand('tldw.sandbox.run', async () => {
    try {
      const serverUrl = vscode.workspace.getConfiguration().get<string>('tldw.sandbox.serverUrl') || 'http://127.0.0.1:8000/api/v1';
      const apiKey = vscode.workspace.getConfiguration().get<string>('tldw.sandbox.apiKey') || '';
      const cmdStr = await vscode.window.showInputBox({ prompt: 'Command to run (JSON array)', value: '["python", "-V"]' });
      if (!cmdStr) { return; }
      let command: string[] = [];
      try { command = JSON.parse(cmdStr); } catch (e) { vscode.window.showErrorMessage('Invalid JSON array'); return; }
      const baseImage = await vscode.window.showInputBox({ prompt: 'Base image (leave empty to use session)', value: 'python:3.11-slim' });
      const body: any = { spec_version: '1.0', command };
      if (baseImage) { body.base_image = baseImage; }

      const url = `${serverUrl.replace(/\/$/, '')}/sandbox/runs`;
      const headers: any = { 'Content-Type': 'application/json' };
      if (apiKey) {
        headers['Authorization'] = apiKey.startsWith('sk-') ? `X-API-KEY ${apiKey}` : (apiKey.startsWith('Bearer ') ? apiKey : `Bearer ${apiKey}`);
      }
      output.appendLine(`POST ${url}`);
      const res = await fetch(url, { method: 'POST', headers, body: JSON.stringify(body) } as any);
      const txt = await res.text();
      output.appendLine(`Status: ${res.status}`);
      output.appendLine(txt);
      output.show(true);
    } catch (e: any) {
      vscode.window.showErrorMessage(`Sandbox run failed: ${e?.message || e}`);
      output.appendLine(String(e));
      output.show(true);
    }
  });

  context.subscriptions.push(disposable);
}

export function deactivate() {}
