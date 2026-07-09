"""Phase 13.1 — offline precision/recall benchmark for the injection detector.

Acceptance:
- A bundled attack+benign corpus scores the *real* SecurityScanner.detect_injection.
- The report exposes precision/recall/F1/accuracy plus the actual FP/FN cases.
- No network is touched with allow_network=False (the air-gap default).
- The upgraded detector clears a high precision AND recall bar on the corpus
  (the pre-upgrade four-pattern detector could not — recall was ~0.27).

Attack strings in the corpus are assembled from split fragments in the module
itself, so this test file needs no contiguous trigger literals.
"""
import urllib.request

from promptwise.security.injection_benchmark import (
    benchmark_injection_detector,
    builtin_corpus,
)


def test_corpus_has_balanced_attack_and_benign_cases():
    corpus = builtin_corpus()
    attacks = [c for c in corpus if c.is_attack]
    benign = [c for c in corpus if not c.is_attack]
    assert len(attacks) >= 10
    assert len(benign) >= 10


def test_report_shape_and_metric_ranges():
    report = benchmark_injection_detector()
    d = report.to_dict()
    assert set(d) >= {
        "total", "attacks", "benign", "tp", "fp", "tn", "fn",
        "precision", "recall", "f1", "accuracy",
        "false_positives", "false_negatives",
    }
    for k in ("precision", "recall", "f1", "accuracy"):
        assert 0.0 <= d[k] <= 1.0


def test_upgraded_detector_clears_precision_and_recall_bar():
    report = benchmark_injection_detector()
    # The original four-pattern detector scored recall ~0.27 / precision 0.80
    # on this corpus; the Phase 13.1 upgrade must clear a high bar on both.
    assert report.recall >= 0.9, report.false_negatives
    assert report.precision >= 0.9, report.false_positives


def test_benchmark_never_touches_network_by_default():
    def _boom(*a, **k):
        raise AssertionError("network access attempted with allow_network=False")

    orig = urllib.request.urlopen
    urllib.request.urlopen = _boom
    try:
        report = benchmark_injection_detector()  # allow_network defaults False
        assert report.total > 0
    finally:
        urllib.request.urlopen = orig


def test_live_pint_fetch_gated_off_by_default():
    from promptwise.security import injection_benchmark as ib

    # With allow_network False the loader returns no live cases regardless of url.
    assert ib._maybe_fetch_pint("https://example.com/pint.json", allow_network=False) == []
