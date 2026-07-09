import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

/**
 * Thin wrapper around the MCP SDK's Client + StdioClientTransport, scoped to
 * exactly what the VS Code panel needs: spawn `python -m promptwise.server`,
 * list its tools, and call a tool expecting a JSON-string result (matching
 * how promptwise.server's handlers already return `json.dumps(...)` strings).
 */
export class McpClient {
  private client: Client | undefined;
  private transport: StdioClientTransport | undefined;

  async connect(pythonPath: string, cwd: string, pythonPathEnv?: string): Promise<void> {
    const env: Record<string, string> = {};
    for (const [k, v] of Object.entries(process.env)) {
      if (v !== undefined) env[k] = v;
    }
    if (pythonPathEnv) env.PYTHONPATH = pythonPathEnv;

    this.transport = new StdioClientTransport({
      command: pythonPath,
      args: ["-m", "promptwise.server"],
      cwd,
      env,
    });
    this.client = new Client({ name: "promptwise-vscode-panel", version: "0.1.0" }, { capabilities: {} });
    await this.client.connect(this.transport);
  }

  async listTools(): Promise<string[]> {
    if (!this.client) throw new Error("mcp client not connected");
    const result = await this.client.listTools();
    return result.tools.map((t) => t.name);
  }

  async callTool(name: string, args: Record<string, unknown> = {}): Promise<string> {
    if (!this.client) throw new Error("mcp client not connected");
    const result = await this.client.callTool({ name, arguments: args });

    // callTool()'s return type is a union: the normal content-bearing result
    // (what every promptwise.server tool returns) or a task-based
    // `{ toolResult: unknown }` shape used by experimental task-execution
    // tools. Narrow with `in` rather than casting to force the assumed shape.
    if (!("content" in result) || !Array.isArray(result.content)) {
      throw new Error(`unexpected tool result shape for ${name}: no content array`);
    }
    const first = result.content[0];
    if (!first || first.type !== "text") {
      throw new Error(`unexpected tool result shape for ${name}: first content block is not text`);
    }
    return first.text;
  }

  async dispose(): Promise<void> {
    await this.transport?.close();
  }
}
