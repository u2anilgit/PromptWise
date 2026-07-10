export function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export interface BudgetTileViewModel {
  spendUsd: number;
  limitUsd: number | null;
  percentUsed: number | null;
  anomalies: string[];
  roiHoursSaved: number;
  error?: string;
}

export function buildBudgetTile(
  budgetStatusJson: string,
  budgetReportJson: string,
  roiReportJson: string
): BudgetTileViewModel {
  try {
    const status = JSON.parse(budgetStatusJson);
    const report = JSON.parse(budgetReportJson);
    // get_roi_report returns a pre-aggregated object (see
    // server.py:_handle_get_roi_report), not a bare array of records.
    const roi = JSON.parse(roiReportJson) as { total_hours_saved?: number };

    const spendUsd = Number(status.spend_usd ?? 0);
    const limitUsd = status.limit_usd === null || status.limit_usd === undefined ? null : Number(status.limit_usd);
    const percentUsed = limitUsd ? Math.round((spendUsd / limitUsd) * 1000) / 10 : null;
    const anomalies = Array.isArray(report.anomalies) ? report.anomalies : [];
    const roiHoursSaved = Number(roi.total_hours_saved) || 0;

    return { spendUsd, limitUsd, percentUsed, anomalies, roiHoursSaved };
  } catch (err) {
    return {
      spendUsd: 0,
      limitUsd: null,
      percentUsed: null,
      anomalies: [],
      roiHoursSaved: 0,
      error: `failed to parse budget data: ${(err as Error).message}`,
    };
  }
}

export function renderBudgetTile(data: BudgetTileViewModel): string {
  if (data.error) return `<p class="error">${escapeHtml(data.error)}</p>`;

  const limitText = data.limitUsd === null ? "no limit set" : `$${data.limitUsd.toFixed(2)}`;
  const progress =
    data.percentUsed === null
      ? ""
      : `<div class="progress"><div class="progress-bar${data.percentUsed >= 100 ? " over" : ""}" style="width:${Math.min(data.percentUsed, 100)}%"></div></div>
         <p class="stat-sub">${data.percentUsed}% used</p>`;
  const anomalies = data.anomalies.length
    ? `<ul>${data.anomalies.map((a) => `<li>${escapeHtml(a)}</li>`).join("")}</ul>`
    : `<p class="muted">No anomalies detected.</p>`;

  return `
    <div class="tile">
      <div class="stat"><span class="stat-label">Spend</span><span class="stat-value">$${data.spendUsd.toFixed(2)}</span></div>
      <div class="stat"><span class="stat-label">Limit</span><span class="stat-value">${limitText}</span></div>
      ${progress}
    </div>
    <div class="tile">
      <div class="stat"><span class="stat-label">ROI hours saved</span><span class="stat-value">${data.roiHoursSaved}</span></div>
    </div>
    <div class="tile">
      <h4>Anomalies</h4>
      ${anomalies}
    </div>
  `;
}

export interface SecurityTileViewModel {
  detectorF1: number | null;
  sbomDependencyCount: number | null;
  sbomKnownCves: number;
  error?: string;
}

export function buildSecurityTile(benchmarkJson: string, sbomJson: string): SecurityTileViewModel {
  try {
    const benchmark = JSON.parse(benchmarkJson);
    const sbom = JSON.parse(sbomJson);

    const detectorF1 = typeof benchmark.f1 === "number" ? benchmark.f1 : null;
    const components = Array.isArray(sbom.components) ? sbom.components : [];
    const vulnerabilities = Array.isArray(sbom.vulnerabilities) ? sbom.vulnerabilities : [];

    return {
      detectorF1,
      sbomDependencyCount: components.length,
      sbomKnownCves: vulnerabilities.length,
    };
  } catch (err) {
    return {
      detectorF1: null,
      sbomDependencyCount: null,
      sbomKnownCves: 0,
      error: `failed to parse security data: ${(err as Error).message}`,
    };
  }
}

export function renderSecurityTile(data: SecurityTileViewModel): string {
  if (data.error) return `<p class="error">${escapeHtml(data.error)}</p>`;

  const f1Text = data.detectorF1 === null ? "n/a" : data.detectorF1.toFixed(2);
  const cveClass = data.sbomKnownCves > 0 ? " warn" : "";

  return `
    <div class="tile">
      <div class="stat"><span class="stat-label">Injection detector F1</span><span class="stat-value">${f1Text}</span></div>
    </div>
    <div class="tile">
      <div class="stat"><span class="stat-label">SBOM dependencies</span><span class="stat-value">${data.sbomDependencyCount ?? "n/a"}</span></div>
      <div class="stat"><span class="stat-label">Known CVEs</span><span class="stat-value${cveClass}">${data.sbomKnownCves}</span></div>
    </div>
  `;
}

export interface GovernanceTileViewModel {
  mode: "advise" | "dry_run" | "apply";
  proposedActions: Array<{ action: string; verdict: string }>;
  error?: string;
}

export function buildGovernanceTile(runGovernorJson: string): GovernanceTileViewModel {
  try {
    const data = JSON.parse(runGovernorJson);
    const mode: "advise" | "dry_run" | "apply" =
      data.mode === "dry_run" || data.mode === "apply" ? data.mode : "advise";
    const proposedActions = Array.isArray(data.actions)
      ? data.actions.map((a: { action: string; verdict: string }) => ({ action: a.action, verdict: a.verdict }))
      : [];

    return { mode, proposedActions };
  } catch (err) {
    return {
      mode: "advise",
      proposedActions: [],
      error: `failed to parse governance data: ${(err as Error).message}`,
    };
  }
}

export function renderGovernanceTile(data: GovernanceTileViewModel): string {
  if (data.error) return `<p class="error">${escapeHtml(data.error)}</p>`;

  const actions = data.proposedActions.length
    ? `<ul>${data.proposedActions
        .map((a) => `<li><strong>${escapeHtml(a.action)}</strong> — ${escapeHtml(a.verdict)}</li>`)
        .join("")}</ul>`
    : `<p class="muted">No actions proposed.</p>`;

  return `
    <div class="tile">
      <div class="stat"><span class="stat-label">Mode</span><span class="badge badge-${data.mode}">${escapeHtml(data.mode)}</span></div>
    </div>
    <div class="tile">
      <h4>Proposed actions</h4>
      ${actions}
    </div>
  `;
}
