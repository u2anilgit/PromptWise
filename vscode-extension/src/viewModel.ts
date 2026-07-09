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
    const roi = JSON.parse(roiReportJson) as Array<{ hours_saved: number }>;

    const spendUsd = Number(status.spend_usd ?? 0);
    const limitUsd = status.limit_usd === null || status.limit_usd === undefined ? null : Number(status.limit_usd);
    const percentUsed = limitUsd ? Math.round((spendUsd / limitUsd) * 1000) / 10 : null;
    const anomalies = Array.isArray(report.anomalies) ? report.anomalies : [];
    const roiHoursSaved = roi.reduce((sum, r) => sum + (Number(r.hours_saved) || 0), 0);

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
