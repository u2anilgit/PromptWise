import { test } from "node:test";
import assert from "node:assert";
import {
  buildBudgetTile,
  buildSecurityTile,
  buildGovernanceTile,
  renderBudgetTile,
  renderSecurityTile,
  renderGovernanceTile,
  escapeHtml,
} from "../src/viewModel.ts";

test("buildBudgetTile shapes a normal response", () => {
  const budgetStatus = JSON.stringify({ spend_usd: 12.4, limit_usd: 50 });
  const budgetReport = JSON.stringify({ anomalies: ["spike on 2026-07-08"] });
  const roiReport = JSON.stringify({ period: "weekly", total_hours_saved: 4.2, total_cost_usd: 1.1, total_tokens_saved: 900, records: [] });

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
  const roiReport = JSON.stringify({ period: "weekly", total_hours_saved: 0, total_cost_usd: 0, total_tokens_saved: 0, records: [] });

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

test("escapeHtml escapes all five reserved characters", () => {
  assert.strictEqual(escapeHtml(`<a href="x">'&'</a>`), "&lt;a href=&quot;x&quot;&gt;&#39;&amp;&#39;&lt;/a&gt;");
});

test("renderBudgetTile shows spend, limit, and progress bar for a normal tile", () => {
  const html = renderBudgetTile({
    spendUsd: 12.4, limitUsd: 50, percentUsed: 24.8, anomalies: ["spike"], roiHoursSaved: 4.2,
  });
  assert.match(html, /\$12\.40/);
  assert.match(html, /\$50\.00/);
  assert.match(html, /24\.8% used/);
  assert.match(html, /<li>spike<\/li>/);
  assert.doesNotMatch(html, /class="error"/);
});

test("renderBudgetTile shows 'no limit set' and no progress bar when limit is null", () => {
  const html = renderBudgetTile({ spendUsd: 0, limitUsd: null, percentUsed: null, anomalies: [], roiHoursSaved: 0 });
  assert.match(html, /no limit set/);
  assert.doesNotMatch(html, /class="progress"/);
  assert.match(html, /No anomalies detected\./);
});

test("renderBudgetTile renders the error state instead of stats", () => {
  const html = renderBudgetTile({
    spendUsd: 0, limitUsd: null, percentUsed: null, anomalies: [], roiHoursSaved: 0, error: "boom",
  });
  assert.strictEqual(html, '<p class="error">boom</p>');
});

test("renderSecurityTile shapes F1 and flags known CVEs", () => {
  const html = renderSecurityTile({ detectorF1: 0.913, sbomDependencyCount: 12, sbomKnownCves: 2 });
  assert.match(html, /0\.91/);
  assert.match(html, /class="stat-value warn">2</);
});

test("renderSecurityTile shows n/a for a null F1 score", () => {
  const html = renderSecurityTile({ detectorF1: null, sbomDependencyCount: null, sbomKnownCves: 0 });
  assert.match(html, /n\/a/);
});

test("renderGovernanceTile shows the mode badge and proposed actions", () => {
  const html = renderGovernanceTile({
    mode: "advise", proposedActions: [{ action: "AdjustBudgetGuard", verdict: "allow" }],
  });
  assert.match(html, /badge-advise/);
  assert.match(html, /<strong>AdjustBudgetGuard<\/strong> — allow/);
});

test("renderGovernanceTile shows a placeholder when no actions are proposed", () => {
  const html = renderGovernanceTile({ mode: "advise", proposedActions: [] });
  assert.match(html, /No actions proposed\./);
});
