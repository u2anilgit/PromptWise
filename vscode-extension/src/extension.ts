import * as vscode from "vscode";
import { PanelProvider } from "./panel.ts";

export function activate(context: vscode.ExtensionContext): void {
  const provider = new PanelProvider(context.extensionUri);
  const disposable = vscode.commands.registerCommand("promptwise.openPanel", () => {
    void provider.show();
  });
  context.subscriptions.push(disposable);
}

export function deactivate(): void {}
