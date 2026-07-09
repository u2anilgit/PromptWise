import { test } from "node:test";
import assert from "node:assert";
import { buildBudgetTile, buildSecurityTile, buildGovernanceTile } from "../src/viewModel.ts";

test("buildBudgetTile shapes a normal response", () => {
  const budgetStatus = JSON.stringify({ spend_usd: 12.4, limit_usd: 50 });
  const budgetReport = JSON.stringify({ anomalies: ["spike on 2026-07-08"] });
  const roiReport = JSON.stringify([{ hours_saved: 2.5 }, { hours_saved: 1.7 }]);

  const tile = buildBudgetTile(budgetStatus, budgetReport, roiReport);

  assert.strictEqual(tile.spendUsd, 12.4);
  assert.strictEqual(tile.limitUsd, 50);
  assert.strictEqual(tile.percentUsed, 24.8);
  assert.deepStrictEqual(tile.anomalies, ["spike on 2026-07-08"]);
  assert.strictEqual(tile.roiHoursSaved, 4.2);
  assert.strictEqual(tile.error, undefined);
});

test("buildBudgetTile handles a missing limit", () => {
  const budgetStatus = JSON.stringify({ spend_usd: 12.4, limit_usd: null });
  const budgetReport = JSON.stringify({ anomalies: [] });
  const roiReport = JSON.stringify([]);

  const tile = buildBudgetTile(budgetStatus, budgetReport, roiReport);

  assert.strictEqual(tile.limitUsd, null);
  assert.strictEqual(tile.percentUsed, null);
  assert.strictEqual(tile.roiHoursSaved, 0);
});

test("buildBudgetTile reports malformed JSON as an error, not a throw", () => {
  const tile = buildBudgetTile("not json", "{}", "[]");
  assert.strictEqual(typeof tile.error, "string");
});

test("buildSecurityTile shapes a normal response", () => {
  const benchmark = JSON.stringify({ f1: 0.91 });
  const sbom = JSON.stringify({ components: [{ name: "a" }, { name: "b" }], vulnerabilities: [] });

  const tile = buildSecurityTile(benchmark, sbom);

  assert.strictEqual(tile.detectorF1, 0.91);
  assert.strictEqual(tile.sbomDependencyCount, 2);
  assert.strictEqual(tile.sbomKnownCves, 0);
  assert.strictEqual(tile.error, undefined);
});

test("buildSecurityTile reports malformed JSON as an error, not a throw", () => {
  const tile = buildSecurityTile("not json", "{}");
  assert.strictEqual(typeof tile.error, "string");
});

test("buildGovernanceTile shapes a normal response", () => {
  const runGovernor = JSON.stringify({
    mode: "advise",
    actions: [{ action: "AdjustBudgetGuard", verdict: "allow" }],
  });

  const tile = buildGovernanceTile(runGovernor);

  assert.strictEqual(tile.mode, "advise");
  assert.deepStrictEqual(tile.proposedActions, [{ action: "AdjustBudgetGuard", verdict: "allow" }]);
  assert.strictEqual(tile.error, undefined);
});

test("buildGovernanceTile reports malformed JSON as an error, not a throw", () => {
  const tile = buildGovernanceTile("not json");
  assert.strictEqual(typeof tile.error, "string");
});
