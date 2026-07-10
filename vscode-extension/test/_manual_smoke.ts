// Manual end-to-end smoke test — NOT part of `npm test` (filename doesn't
// match test/*.test.ts, and it needs a real python -m promptwise.server).
// Drives the real MCP round trip through the exact McpClient + viewModel
// code the webview panel uses, catching shape mismatches the mocked unit
// tests can't (this is how the get_roi_report array-vs-object bug was found
// — see viewModel.ts). Run directly: node test/_manual_smoke.ts
import path from "node:path";
import { McpClient } from "../src/mcpClient.ts";
import { buildBudgetTile, buildSecurityTile, buildGovernanceTile } from "../src/viewModel.ts";

const REPO_ROOT = path.resolve(import.meta.dirname, "..", "..");

async function main() {
  const client = new McpClient();
  await client.connect("python", REPO_ROOT);

  const tools = await client.listTools();
  console.log(`listTools: ${tools.length} tools`);
  for (const name of ["get_budget_status", "budget_report", "get_roi_report", "benchmark_injection", "get_sbom", "run_governor"]) {
    if (!tools.includes(name)) throw new Error(`missing expected tool: ${name}`);
  }

  const [status, report, roi] = await Promise.all([
    client.callTool("get_budget_status"),
    client.callTool("budget_report"),
    client.callTool("get_roi_report"),
  ]);
  console.log("raw get_roi_report:", roi.slice(0, 500));
  const budget = buildBudgetTile(status, report, roi);
  console.log("budget tile:", JSON.stringify(budget));
  if (budget.error) throw new Error(`budget tile error: ${budget.error}`);

  const [benchmark, sbom] = await Promise.all([
    client.callTool("benchmark_injection"),
    client.callTool("get_sbom"),
  ]);
  console.log("raw get_sbom:", sbom.slice(0, 500));
  const security = buildSecurityTile(benchmark, sbom);
  console.log("security tile:", JSON.stringify(security));
  if (security.error) throw new Error(`security tile error: ${security.error}`);

  const runGovernor = await client.callTool("run_governor");
  const governance = buildGovernanceTile(runGovernor);
  console.log("governance tile:", JSON.stringify(governance));
  if (governance.error) throw new Error(`governance tile error: ${governance.error}`);

  // on-demand scan path used by the Security tab's "scan pasted text" input —
  // benign text is enough to prove the round trip works end to end.
  const scan = await client.callTool("security_check", { text: "hello world", code: "hello world" });
  console.log("security_check (on-demand scan):", scan.slice(0, 200));

  await client.dispose();
  console.log("SMOKE TEST PASSED");
}

main().catch((err) => {
  console.error("SMOKE TEST FAILED:", err);
  process.exit(1);
});
