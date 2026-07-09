# PromptWise Panel (VS Code extension)

Local Budget/Security/Governance dashboard for PromptWise, talking to the
existing `promptwise` MCP server over stdio — no external services, no
network calls, no daemon.

## Requirements

- A PromptWise checkout with `pip install -e .` already run (or a system
  `python` where `promptwise` is importable).

## Settings

- `promptwise.pythonPath` (default `"python"`) — interpreter used to launch
  the server.
- `promptwise.workspaceRoot` (default `"${workspaceFolder}"`) — root of the
  PromptWise checkout.

## Build and install locally

```bash
npm install
npm run package
code --install-extension promptwise-panel-0.1.0.vsix
```

Then run the command **PromptWise: Open Panel**.

## Development

```bash
npm install
npm run compile   # build
node --test test/*.test.ts   # unit tests
```

No `@vscode/test-electron` / real-editor-launch integration tests in this
package — verify the webview renders correctly by installing the built
`.vsix` and opening the panel manually.
