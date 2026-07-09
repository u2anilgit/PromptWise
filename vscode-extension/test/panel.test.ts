import { test } from "node:test";
import assert from "node:assert";
import { handleWebviewMessage, PendingMessageQueue } from "../src/panel.ts";

function fakeClient(responses: Record<string, string>) {
  return {
    async callTool(name: string): Promise<string> {
      if (!(name in responses)) throw new Error(`no fake response for ${name}`);
      return responses[name];
    },
  };
}

test("refresh budget calls the 3 budget tools it actually uses and returns a tileUpdate", async () => {
  const client = fakeClient({
    get_budget_status: JSON.stringify({ spend_usd: 10, limit_usd: 100 }),
    budget_report: JSON.stringify({ anomalies: [] }),
    get_roi_report: JSON.stringify([]),
  });

  const result = await handleWebviewMessage({ type: "refresh", tab: "budget" }, client);

  assert.strictEqual(result.type, "tileUpdate");
  assert.strictEqual((result as { tab: string }).tab, "budget");
});

test("refresh security calls benchmark_injection + get_sbom and returns a tileUpdate", async () => {
  const client = fakeClient({
    benchmark_injection: JSON.stringify({ f1: 0.9 }),
    get_sbom: JSON.stringify({ components: [], vulnerabilities: [] }),
  });

  const result = await handleWebviewMessage({ type: "refresh", tab: "security" }, client);

  assert.strictEqual(result.type, "tileUpdate");
  assert.strictEqual((result as { tab: string }).tab, "security");
});

test("refresh governance calls run_governor and returns a tileUpdate", async () => {
  const client = fakeClient({
    run_governor: JSON.stringify({ mode: "advise", actions: [] }),
  });

  const result = await handleWebviewMessage({ type: "refresh", tab: "governance" }, client);

  assert.strictEqual(result.type, "tileUpdate");
  assert.strictEqual((result as { tab: string }).tab, "governance");
});

test("a failing tool call produces a tileError, not a throw", async () => {
  const client = fakeClient({}); // every callTool throws "no fake response"

  const result = await handleWebviewMessage({ type: "refresh", tab: "budget" }, client);

  assert.strictEqual(result.type, "tileError");
  assert.strictEqual((result as { tab: string }).tab, "budget");
});

test("scanText calls the named tool and returns a scanResult", async () => {
  const client = fakeClient({ security_check: JSON.stringify({ findings: [] }) });

  const result = await handleWebviewMessage(
    { type: "scanText", kind: "security_check", text: "some code" },
    client
  );

  assert.strictEqual(result.type, "scanResult");
});

test("PendingMessageQueue buffers messages sent before markReady()", () => {
  const queue = new PendingMessageQueue();

  const result = queue.enqueueOrPass({ type: "connectionError", message: "not ready yet" });

  assert.deepStrictEqual(result, []);
});

test("PendingMessageQueue.markReady() flushes buffered messages in order", () => {
  const queue = new PendingMessageQueue();
  const first = { type: "connectionError", message: "first" } as const;
  const second = { type: "scanResult", text: "second" } as const;

  queue.enqueueOrPass(first);
  queue.enqueueOrPass(second);
  const flushed = queue.markReady();

  assert.deepStrictEqual(flushed, [first, second]);
});

test("PendingMessageQueue passes messages straight through after markReady()", () => {
  const queue = new PendingMessageQueue();
  queue.markReady();

  const message = { type: "scanResult", text: "live" } as const;
  const result = queue.enqueueOrPass(message);

  assert.deepStrictEqual(result, [message]);
});

test("PendingMessageQueue.markReady() called with an empty queue returns an empty array", () => {
  const queue = new PendingMessageQueue();

  assert.deepStrictEqual(queue.markReady(), []);
});
