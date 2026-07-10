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
package — visually confirm the webview by installing the built `.vsix` and
opening the panel manually. For a backend-only check (no editor needed),
`node test/_manual_smoke.ts` drives the real `McpClient` against a real
`python -m promptwise.server`, exactly the path the webview uses — it
caught a real tool-output shape mismatch (`get_roi_report`) that the mocked
unit tests missed, and stays around to catch the next one.
