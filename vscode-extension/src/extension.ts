import * as vscode from "vscode";

export function activate(context: vscode.ExtensionContext): void {
  const disposable = vscode.commands.registerCommand("promptwise.openPanel", () => {
    vscode.window.showInformationMessage("PromptWise Panel: not yet implemented.");
  });
  context.subscriptions.push(disposable);
}

export function deactivate(): void {}
