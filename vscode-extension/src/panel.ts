// Type-only import: the real "vscode" module is only resolvable inside the
// VS Code extension host, not under plain `node --test`. Keeping this
// type-only (erased entirely at compile time) lets test/panel.test.ts import
// handleWebviewMessage without triggering module resolution of "vscode".
// PanelProvider.show() below does a runtime `await import("vscode")` instead,
// which only ever executes inside the real extension host.
import type * as vscode from "vscode";
import * as fs from "node:fs";
import * as path from "node:path";
import { McpClient } from "./mcpClient.ts";
import { buildBudgetTile, buildSecurityTile, buildGovernanceTile } from "./viewModel.ts";

export type Tab = "budget" | "security" | "governance";

export type HostToWebviewMessage =
  | { type: "tileUpdate"; tab: Tab; data: unknown }
  | { type: "tileError"; tab: Tab; message: string }
  | { type: "connectionError"; message: string }
  | { type: "scanResult"; text: string };

export type WebviewToHostMessage =
  | { type: "refresh"; tab: Tab }
  | { type: "scanText"; kind: "security_check"; text: string }
  | { type: "ready" };

/**
 * Buffers HostToWebviewMessages until the webview signals it is ready to
 * receive them (via an incoming `{ type: "ready" }` message), so a message
 * sent immediately after `panel.webview.html = ...` can't race the
 * webview's `window.addEventListener("message", ...)` registration.
 * Deliberately has no `vscode` dependency so it's directly unit-testable.
 */
export class PendingMessageQueue {
  private ready = false;
  private queue: HostToWebviewMessage[] = [];

  markReady(): HostToWebviewMessage[] {
    this.ready = true;
    const flushed = this.queue;
    this.queue = [];
    return flushed;
  }

  enqueueOrPass(message: HostToWebviewMessage): HostToWebviewMessage[] {
    if (this.ready) return [message];
    this.queue.push(message);
    return [];
  }
}

interface ToolCaller {
  callTool(name: string, args?: Record<string, unknown>): Promise<string>;
}

export async function handleWebviewMessage(
  message: Exclude<WebviewToHostMessage, { type: "ready" }>,
  client: ToolCaller
): Promise<HostToWebviewMessage> {
  if (message.type === "scanText") {
    try {
      const result = await client.callTool(message.kind, { text: message.text, code: message.text });
      return { type: "scanResult", text: result };
    } catch (err) {
      return { type: "scanResult", text: JSON.stringify({ error: (err as Error).message }) };
    }
  }

  const tab = message.tab;
  try {
    if (tab === "budget") {
      const [status, report, roi] = await Promise.all([
        client.callTool("get_budget_status"),
        client.callTool("budget_report"),
        client.callTool("get_roi_report"),
      ]);
      return { type: "tileUpdate", tab, data: buildBudgetTile(status, report, roi) };
    }
    if (tab === "security") {
      const [benchmark, sbom] = await Promise.all([
        client.callTool("benchmark_injection"),
        client.callTool("get_sbom"),
      ]);
      return { type: "tileUpdate", tab, data: buildSecurityTile(benchmark, sbom) };
    }
    // tab === "governance"
    const runGovernor = await client.callTool("run_governor");
    return { type: "tileUpdate", tab, data: buildGovernanceTile(runGovernor) };
  } catch (err) {
    return { type: "tileError", tab, message: (err as Error).message };
  }
}

export class PanelProvider {
  private panel: vscode.WebviewPanel | undefined;
  private client: McpClient | undefined;
  private readonly extensionUri: vscode.Uri;
  private readonly pending = new PendingMessageQueue();

  constructor(extensionUri: vscode.Uri) {
    this.extensionUri = extensionUri;
  }

  async show(): Promise<void> {
    const vscodeApi = await import("vscode");

    if (this.panel) {
      this.panel.reveal();
      return;
    }

    this.panel = vscodeApi.window.createWebviewPanel(
      "promptwisePanel",
      "PromptWise",
      vscodeApi.ViewColumn.One,
      { enableScripts: true, retainContextWhenHidden: true }
    );

    const config = vscodeApi.workspace.getConfiguration("promptwise");
    const pythonPath = config.get<string>("pythonPath", "python");
    const workspaceRoot = config.get<string>("workspaceRoot", "${workspaceFolder}");
    const resolvedRoot =
      vscodeApi.workspace.workspaceFolders?.[0]?.uri.fsPath ?? process.cwd();
    const cwd = workspaceRoot.includes("${workspaceFolder}") ? resolvedRoot : workspaceRoot;

    const webviewUri = this.panel.webview.asWebviewUri(
      vscodeApi.Uri.joinPath(this.extensionUri, "dist", "webview", "main.js")
    );
    const styleUri = this.panel.webview.asWebviewUri(
      vscodeApi.Uri.joinPath(this.extensionUri, "dist", "webview", "style.css")
    );

    const srcPromptwise = path.join(cwd, "src", "promptwise");
    const pythonPathEnv = fs.existsSync(srcPromptwise) ? path.join(cwd, "src") : undefined;

    // Register the message listener (and its "ready" handshake handling)
    // before doing anything else that might post a message, so a
    // connectionError posted below is never lost: it's buffered in
    // `this.pending` until the webview's "ready" ping flushes it.
    this.panel.webview.onDidReceiveMessage(async (message: WebviewToHostMessage) => {
      if (message.type === "ready") {
        for (const flushed of this.pending.markReady()) {
          void this.panel?.webview.postMessage(flushed);
        }
        return;
      }
      if (!this.client) return;
      const response = await handleWebviewMessage(message, this.client);
      this.postMessage(response);
    });

    this.panel.onDidDispose(() => {
      void this.client?.dispose();
      this.client = undefined;
      this.panel = undefined;
    });

    this.client = new McpClient();
    try {
      await this.client.connect(pythonPath, cwd, pythonPathEnv);
    } catch (err) {
      this.panel.webview.html = this.renderHtml(webviewUri.toString(), styleUri.toString());
      this.postMessage({ type: "connectionError", message: (err as Error).message });
      return;
    }

    this.panel.webview.html = this.renderHtml(webviewUri.toString(), styleUri.toString());
  }

  private postMessage(message: HostToWebviewMessage): void {
    for (const toSend of this.pending.enqueueOrPass(message)) {
      void this.panel?.webview.postMessage(toSend);
    }
  }

  private renderHtml(webviewUri: string, styleUri: string): string {
    return `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8" />
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src ${this.panel!.webview.cspSource}; style-src ${this.panel!.webview.cspSource} 'unsafe-inline';" />
  <link rel="stylesheet" href="${styleUri}" />
</head>
<body>
  <div id="app"></div>
  <script src="${webviewUri}"></script>
</body>
</html>`;
  }
}
