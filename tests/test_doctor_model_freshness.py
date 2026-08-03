from promptwise.core.doctor import run_diagnostics


def test_model_catalog_freshness_check_present_and_never_fails_overall(tmp_path):
    report = run_diagnostics(cwd=tmp_path)
    names = [c["check"] for c in report["checks"]]
    assert "model catalog freshness" in names
    freshness = next(c for c in report["checks"] if c["check"] == "model catalog freshness")
    # Advisory only -- staleness/missing data must never fail this check.
    assert freshness["ok"] is True
