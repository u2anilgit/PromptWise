// Type-only import: the real "vscode" module is only resolvable inside the
// VS Code extension host, not under plain `node --test`. Keeping this
// type-only (erased entirely at compile time) lets test/panel.test.ts import
// handleWebviewMessage without triggering module resolution of "vscode".
// PanelProvider.show() below does a runtime `await import("vscode")` instead,
// which only ever executes inside the real extension host.
import type * as vscode from "vscode";
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
  | { type: "scanText"; kind: "security_check" | "owasp_scan" | "prompt_injection"; text: string };

interface ToolCaller {
  callTool(name: string, args?: Record<string, unknown>): Promise<string>;
}

export async function handleWebviewMessage(
  message: WebviewToHostMessage,
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
      const [status, report, cost, roi, task] = await Promise.all([
        client.callTool("get_budget_status"),
        client.callTool("budget_report"),
        client.callTool("cost_report"),
        client.callTool("get_roi_report"),
        client.callTool("task_report"),
      ]);
      void cost;
      void task;
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

    this.client = new McpClient();
    try {
      await this.client.connect(pythonPath, cwd);
    } catch (err) {
      this.panel.webview.html = this.renderHtml(webviewUri.toString());
      this.postMessage({ type: "connectionError", message: (err as Error).message });
      return;
    }

    this.panel.webview.html = this.renderHtml(webviewUri.toString());
    this.panel.webview.onDidReceiveMessage(async (message: WebviewToHostMessage) => {
      if (!this.client) return;
      const response = await handleWebviewMessage(message, this.client);
      this.postMessage(response);
    });

    this.panel.onDidDispose(() => {
      void this.client?.dispose();
      this.client = undefined;
      this.panel = undefined;
    });
  }

  private postMessage(message: HostToWebviewMessage): void {
    void this.panel?.webview.postMessage(message);
  }

  private renderHtml(webviewUri: string): string {
    return `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8" />
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src ${this.panel!.webview.cspSource}; style-src ${this.panel!.webview.cspSource} 'unsafe-inline';" />
</head>
<body>
  <div id="app"></div>
  <script src="${webviewUri}"></script>
</body>
</html>`;
  }
}
