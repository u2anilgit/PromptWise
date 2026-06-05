# Installing PromptWise

## Quick install
pip install -e .

## Register MCP servers in .mcp.json
Add to your Claude Code project's .mcp.json:
```json
{
  "mcpServers": {
    "promptwise": {
      "command": "python",
      "args": ["-m", "promptwise.server"]
    },
    "promptwise-v2": {
      "command": "python",
      "args": ["-m", "promptwise_v2.integrations.mcp_server_v2"]
    }
  }
}
```

## Verify installation
Run: python -m promptwise.server --help
