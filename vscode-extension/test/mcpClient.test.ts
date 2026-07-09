// vscode-extension/test/mcpClient.test.ts
import { test } from "node:test";
import assert from "node:assert";
import path from "node:path";
import { McpClient } from "../src/mcpClient.ts";

// Repo root is two levels up from vscode-extension/test/.
const REPO_ROOT = path.resolve(import.meta.dirname, "..", "..");

test("connects to the real promptwise MCP server and lists tools", async (t) => {
  const client = new McpClient();
  try {
    await client.connect("python", REPO_ROOT);
  } catch (err) {
    t.skip(`python -m promptwise.server not available in this environment: ${err}`);
    return;
  }
  try {
    const tools = await client.listTools();
    assert.ok(tools.length > 0, "expected at least one tool");
    assert.ok(tools.includes("get_budget_status"), "expected get_budget_status to be registered");
  } finally {
    await client.dispose();
  }
});

test("calls get_budget_status and gets a JSON string result", async (t) => {
  const client = new McpClient();
  try {
    await client.connect("python", REPO_ROOT);
  } catch (err) {
    t.skip(`python -m promptwise.server not available in this environment: ${err}`);
    return;
  }
  try {
    const result = await client.callTool("get_budget_status");
    assert.strictEqual(typeof result, "string");
    const parsed = JSON.parse(result);
    assert.strictEqual(typeof parsed, "object");
  } finally {
    await client.dispose();
  }
});
