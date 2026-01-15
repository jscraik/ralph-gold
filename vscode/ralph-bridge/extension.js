/* eslint-disable */
// Ralph Bridge VS Code extension (no build step)
// Communicates with `ralph bridge` using JSON-RPC 2.0 over stdio (NDJSON).

const vscode = require('vscode');
const cp = require('child_process');
const readline = require('readline');

class BridgeClient {
  /**
   * @param {string} root
   * @param {vscode.OutputChannel} output
   * @param {(status: any) => void} onStatus
   */
  constructor(root, output, onStatus) {
    this.root = root;
    this.output = output;
    this.onStatus = onStatus;
    this.proc = null;
    this.rl = null;
    this.nextId = 1;
    this.pending = new Map();
  }

  isRunning() {
    return this.proc && !this.proc.killed;
  }

  start() {
    if (this.isRunning()) {
      return;
    }

    const cfg = vscode.workspace.getConfiguration('ralph');
    const cmd = cfg.get('bridgeCommand') || 'ralph';

    this.output.appendLine(`[bridge] starting: ${cmd} bridge (cwd=${this.root})`);

    this.proc = cp.spawn(cmd, ['bridge'], {
      cwd: this.root,
      shell: true,
      stdio: ['pipe', 'pipe', 'pipe']
    });

    this.proc.on('exit', (code, signal) => {
      this.output.appendLine(`[bridge] exited code=${code} signal=${signal}`);
      // reject all pending
      for (const [id, p] of this.pending.entries()) {
        p.reject(new Error(`bridge exited (id=${id})`));
      }
      this.pending.clear();
      this.proc = null;
      if (this.rl) {
        try { this.rl.close(); } catch (_) {}
        this.rl = null;
      }
    });

    this.proc.stderr.on('data', (chunk) => {
      const s = String(chunk || '').trimEnd();
      if (s) this.output.appendLine(`[bridge:stderr] ${s}`);
    });

    this.rl = readline.createInterface({ input: this.proc.stdout });
    this.rl.on('line', (line) => {
      const trimmed = String(line || '').trim();
      if (!trimmed) return;
      let msg;
      try {
        msg = JSON.parse(trimmed);
      } catch (e) {
        this.output.appendLine(`[bridge] non-json: ${trimmed}`);
        return;
      }

      // Response
      if (Object.prototype.hasOwnProperty.call(msg, 'id')) {
        const id = msg.id;
        const pending = this.pending.get(id);
        if (!pending) return;
        this.pending.delete(id);
        if (msg.error) {
          const err = new Error(msg.error.message || 'JSON-RPC error');
          err.code = msg.error.code;
          err.data = msg.error.data;
          pending.reject(err);
        } else {
          pending.resolve(msg.result);
        }
        return;
      }

      // Notification
      if (msg.method === 'event' && msg.params) {
        const ev = msg.params;
        const t = ev.type || 'event';
        this.output.appendLine(`[event:${t}] ${JSON.stringify(ev)}`);
        // Opportunistic status refresh on interesting events
        if (t === 'bridge_started' || t === 'iteration_finished' || t === 'run_stopped') {
          this.status().then((st) => this.onStatus(st)).catch(() => {});
        }
        return;
      }

      this.output.appendLine(`[bridge] notify: ${JSON.stringify(msg)}`);
    });
  }

  stop() {
    if (!this.proc) return;
    this.output.appendLine('[bridge] stopping');
    try {
      this.proc.kill();
    } catch (_) {}
  }

  request(method, params) {
    if (!this.proc) {
      throw new Error('Bridge not started');
    }
    const id = this.nextId++;
    const msg = { jsonrpc: '2.0', id, method, params: params || {} };
    const line = JSON.stringify(msg);
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.proc.stdin.write(line + '\n');
    });
  }

  ping() { return this.request('ping', {}); }
  status() { return this.request('status', {}); }
  step(agent) { return this.request('step', { agent: agent || 'codex' }); }
  run(agent, maxIterations) {
    const params = { agent: agent || 'codex' };
    if (typeof maxIterations === 'number') params.maxIterations = maxIterations;
    return this.request('run', params);
  }
  stopRun() { return this.request('stop', {}); }
  pause() { return this.request('pause', {}); }
  resume() { return this.request('resume', {}); }
}

/**
 * @param {vscode.ExtensionContext} context
 */
function activate(context) {
  const output = vscode.window.createOutputChannel('Ralph');
  context.subscriptions.push(output);

  let client = null;
  let statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  statusBar.text = 'Ralph: (idle)';
  statusBar.tooltip = 'Ralph Bridge status';
  statusBar.command = 'ralph.status';
  statusBar.show();
  context.subscriptions.push(statusBar);

  const updateStatusBar = (st) => {
    try {
      if (!st) {
        statusBar.text = 'Ralph: (unknown)';
        return;
      }
      const done = st.done ?? 0;
      const total = st.total ?? 0;
      const running = st.running ? (st.paused ? 'paused' : 'running') : 'idle';
      const next = st.next ? `next:${st.next.id}` : '';
      statusBar.text = `Ralph: ${done}/${total} ${running} ${next}`.trim();
    } catch (_) {
      statusBar.text = 'Ralph: (status error)';
    }
  };

  const getWorkspaceRoot = () => {
    const folders = vscode.workspace.workspaceFolders || [];
    if (!folders.length) return null;
    return folders[0].uri.fsPath;
  };

  const ensureBridge = async () => {
    if (client && client.isRunning()) return client;
    const root = getWorkspaceRoot();
    if (!root) {
      vscode.window.showErrorMessage('Ralph: Open a folder/workspace first.');
      return null;
    }
    client = new BridgeClient(root, output, updateStatusBar);
    client.start();
    // Wait for ping to validate
    try {
      await client.ping();
      const st = await client.status();
      updateStatusBar(st);
      output.show(true);
    } catch (e) {
      vscode.window.showErrorMessage(`Ralph bridge failed to start: ${e.message || e}`);
      client.stop();
      client = null;
      return null;
    }
    return client;
  };

  context.subscriptions.push(
    vscode.commands.registerCommand('ralph.startBridge', async () => {
      await ensureBridge();
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('ralph.stopBridge', async () => {
      if (client) {
        client.stop();
        client = null;
        statusBar.text = 'Ralph: (idle)';
      }
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('ralph.status', async () => {
      const c = await ensureBridge();
      if (!c) return;
      try {
        const st = await c.status();
        updateStatusBar(st);
        output.appendLine(`[status] ${JSON.stringify(st)}`);
        output.show(true);
      } catch (e) {
        vscode.window.showErrorMessage(`Ralph status failed: ${e.message || e}`);
      }
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('ralph.step', async () => {
      const c = await ensureBridge();
      if (!c) return;
      const agent = await vscode.window.showQuickPick(['codex', 'claude', 'copilot'], {
        title: 'Pick an agent runner',
        placeHolder: 'codex'
      });
      if (!agent) return;
      try {
        const res = await c.step(agent);
        output.appendLine(`[step] ${JSON.stringify(res)}`);
        const st = await c.status();
        updateStatusBar(st);
        output.show(true);
      } catch (e) {
        vscode.window.showErrorMessage(`Ralph step failed: ${e.message || e}`);
      }
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('ralph.run', async () => {
      const c = await ensureBridge();
      if (!c) return;
      const agent = await vscode.window.showQuickPick(['codex', 'claude', 'copilot'], {
        title: 'Pick an agent runner',
        placeHolder: 'codex'
      });
      if (!agent) return;
      const maxStr = await vscode.window.showInputBox({
        title: 'Max iterations (optional)',
        prompt: 'Leave blank to use loop.max_iterations from ralph.toml'
      });
      let maxIter = undefined;
      if (maxStr && String(maxStr).trim()) {
        const n = Number(maxStr);
        if (Number.isFinite(n) && n > 0) maxIter = Math.floor(n);
        else {
          vscode.window.showErrorMessage('Max iterations must be a positive integer');
          return;
        }
      }
      try {
        const res = await c.run(agent, maxIter);
        output.appendLine(`[run] started ${JSON.stringify(res)}`);
        const st = await c.status();
        updateStatusBar(st);
        output.show(true);
      } catch (e) {
        vscode.window.showErrorMessage(`Ralph run failed: ${e.message || e}`);
      }
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('ralph.stop', async () => {
      const c = await ensureBridge();
      if (!c) return;
      try {
        const res = await c.stopRun();
        output.appendLine(`[stop] ${JSON.stringify(res)}`);
        const st = await c.status();
        updateStatusBar(st);
      } catch (e) {
        vscode.window.showErrorMessage(`Ralph stop failed: ${e.message || e}`);
      }
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('ralph.pause', async () => {
      const c = await ensureBridge();
      if (!c) return;
      try {
        const res = await c.pause();
        output.appendLine(`[pause] ${JSON.stringify(res)}`);
        const st = await c.status();
        updateStatusBar(st);
      } catch (e) {
        vscode.window.showErrorMessage(`Ralph pause failed: ${e.message || e}`);
      }
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('ralph.resume', async () => {
      const c = await ensureBridge();
      if (!c) return;
      try {
        const res = await c.resume();
        output.appendLine(`[resume] ${JSON.stringify(res)}`);
        const st = await c.status();
        updateStatusBar(st);
      } catch (e) {
        vscode.window.showErrorMessage(`Ralph resume failed: ${e.message || e}`);
      }
    })
  );

  // --- Convenience commands that shell out to the CLI ---

  context.subscriptions.push(
    vscode.commands.registerCommand('ralph.specsCheck', async () => {
      const root = getWorkspaceRoot();
      if (!root) {
        vscode.window.showErrorMessage('Ralph: Open a folder/workspace first.');
        return;
      }

      const cfg = vscode.workspace.getConfiguration('ralph');
      const cmd = cfg.get('bridgeCommand') || 'ralph';

      output.appendLine(`[specs] running: ${cmd} specs check (cwd=${root})`);
      const p = cp.spawn(cmd, ['specs', 'check'], { cwd: root, shell: true, stdio: ['ignore', 'pipe', 'pipe'] });
      p.stdout.on('data', (chunk) => output.append(String(chunk || '')));
      p.stderr.on('data', (chunk) => output.append(String(chunk || '')));
      p.on('exit', (code) => {
        output.appendLine(`\n[specs] exited code=${code}`);
        output.show(true);
      });
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('ralph.regenPlan', async () => {
      const root = getWorkspaceRoot();
      if (!root) {
        vscode.window.showErrorMessage('Ralph: Open a folder/workspace first.');
        return;
      }

      const agent = await vscode.window.showQuickPick(['claude', 'codex', 'copilot'], {
        title: 'Pick an agent runner for planning',
        placeHolder: 'claude'
      });
      if (!agent) return;

      const cfg = vscode.workspace.getConfiguration('ralph');
      const cmd = cfg.get('bridgeCommand') || 'ralph';

      output.appendLine(`[regen-plan] running: ${cmd} regen-plan --agent ${agent} (cwd=${root})`);
      const p = cp.spawn(cmd, ['regen-plan', '--agent', agent], { cwd: root, shell: true, stdio: ['ignore', 'pipe', 'pipe'] });
      p.stdout.on('data', (chunk) => output.append(String(chunk || '')));
      p.stderr.on('data', (chunk) => output.append(String(chunk || '')));
      p.on('exit', (code) => {
        output.appendLine(`\n[regen-plan] exited code=${code}`);
        output.show(true);
      });
    })
  );
}

function deactivate() {
  // no-op (bridge process is owned by the extension host; it will exit on reload)
}

module.exports = {
  activate,
  deactivate
};
