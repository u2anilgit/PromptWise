import pytest


@pytest.fixture(autouse=True)
def _isolate_promptwise_db(tmp_path, monkeypatch):
    """Redirect promptwise.db.models.get_db_path() to a per-test temp
    directory for every test in the suite. Without this, any code path
    that constructs RiskRegister()/SecurityScanStore()/etc. with no
    explicit db_path resolves to the real ~/.promptwise/promptwise.db,
    silently writing test data (or, at minimum, creating tables) in the
    real user database. See tests/test_security_handlers.py and
    tests/test_compliance_export.py for the same fix applied narrowly
    before this fixture existed. A test's own monkeypatch.setattr on the
    same target (they share pytest's function-scoped monkeypatch fixture)
    simply layers on top and wins for that test's duration."""
    monkeypatch.setattr("promptwise.db.models.get_db_path", lambda: tmp_path / "promptwise.db")
