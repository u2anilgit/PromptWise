"""core/alerts - opt-in Slack/webhook/email notification on budget or security
threshold crossings. Zero coupling to plugins/budget.py or security/scanner.py:
alerts subscribe to the typed results (BudgetStatus, SecurityResult) those
modules already return from check(), never their internals. Off by default;
every send is fail-soft.
"""
from __future__ import annotations

from promptwise.core import alerts
from promptwise.types import BudgetStatus, SecurityResult


def _budget(alert_level="ok", pct=10.0) -> BudgetStatus:
    return BudgetStatus(used_usd=1.0, limit_usd=10.0, pct_used=pct,
                        daily_burn_usd=0.1, projected_monthly_usd=3.0,
                        alert_level=alert_level, project_id=None)


def _security(blocked=False, risk=0.1, violations=None) -> SecurityResult:
    return SecurityResult(passed=not violations, checks_run=["secrets"],
                          violations=violations or [], risk_score=risk,
                          blocked=blocked, details="")


def test_default_config_is_disabled():
    cfg = alerts.AlertConfig()
    assert cfg.enabled is False


def test_load_alert_config_missing_file_returns_disabled_default(tmp_path):
    cfg = alerts.load_alert_config(tmp_path / "does_not_exist.yaml")
    assert cfg.enabled is False


def test_load_alert_config_reads_yaml(tmp_path):
    p = tmp_path / "alerts.yaml"
    p.write_text(
        "enabled: true\n"
        "budget_min_level: warn\n"
        "security_min_risk: 0.5\n"
        "channels:\n"
        "  webhook:\n"
        "    enabled: true\n"
        "    url: https://hooks.example.invalid/wh1\n",
        encoding="utf-8",
    )
    cfg = alerts.load_alert_config(p)
    assert cfg.enabled is True
    assert cfg.budget_min_level == "warn"
    assert cfg.security_min_risk == 0.5
    assert cfg.channels["webhook"]["enabled"] is True
    assert cfg.channels["webhook"]["url"] == "https://hooks.example.invalid/wh1"


def test_load_alert_config_malformed_yaml_fails_soft(tmp_path):
    p = tmp_path / "alerts.yaml"
    p.write_text("not: [valid: yaml: at all", encoding="utf-8")
    cfg = alerts.load_alert_config(p)
    assert cfg.enabled is False


def test_notify_budget_noop_when_disabled():
    cfg = alerts.AlertConfig(enabled=False)
    result = alerts.notify_budget(_budget(alert_level="hard_stop"), config=cfg)
    assert result["sent"] is False
    assert result["reason"] == "disabled"


def test_notify_budget_noop_below_threshold():
    cfg = alerts.AlertConfig(enabled=True, budget_min_level="critical",
                             channels={"webhook": {"enabled": True, "url": "https://hooks.example.invalid/wh1"}})
    result = alerts.notify_budget(_budget(alert_level="warn"), config=cfg)
    assert result["sent"] is False
    assert result["reason"] == "below_threshold"


def test_notify_budget_fires_at_or_above_threshold(monkeypatch):
    sent = []
    monkeypatch.setattr(alerts, "_send_webhook", lambda url, payload: sent.append((url, payload)) or True)
    cfg = alerts.AlertConfig(enabled=True, budget_min_level="critical",
                             channels={"webhook": {"enabled": True, "url": "https://hooks.example.invalid/wh1"}})
    result = alerts.notify_budget(_budget(alert_level="critical", pct=91.0), config=cfg)
    assert result["sent"] is True
    assert "webhook" in result["channels"]
    assert len(sent) == 1
    assert sent[0][0] == "https://hooks.example.invalid/wh1"
    assert sent[0][1]["alert_level"] == "critical"


def test_notify_budget_hard_stop_always_fires_when_min_is_warn(monkeypatch):
    monkeypatch.setattr(alerts, "_send_webhook", lambda url, payload: True)
    cfg = alerts.AlertConfig(enabled=True, budget_min_level="warn",
                             channels={"webhook": {"enabled": True, "url": "https://hooks.example.invalid/wh1"}})
    result = alerts.notify_budget(_budget(alert_level="hard_stop"), config=cfg)
    assert result["sent"] is True


def test_notify_security_noop_when_clean():
    cfg = alerts.AlertConfig(enabled=True, security_min_risk=0.7,
                             channels={"webhook": {"enabled": True, "url": "https://hooks.example.invalid/wh1"}})
    result = alerts.notify_security(_security(blocked=False, risk=0.1), config=cfg)
    assert result["sent"] is False


def test_notify_security_fires_when_blocked(monkeypatch):
    monkeypatch.setattr(alerts, "_send_webhook", lambda url, payload: True)
    cfg = alerts.AlertConfig(enabled=True, security_min_risk=0.7,
                             channels={"webhook": {"enabled": True, "url": "https://hooks.example.invalid/wh1"}})
    result = alerts.notify_security(_security(blocked=True, risk=0.9,
                                              violations=[{"check": "syntax", "detail": "x"}]), config=cfg)
    assert result["sent"] is True


def test_notify_security_fires_above_risk_threshold_even_if_not_blocked(monkeypatch):
    monkeypatch.setattr(alerts, "_send_webhook", lambda url, payload: True)
    cfg = alerts.AlertConfig(enabled=True, security_min_risk=0.5,
                             channels={"webhook": {"enabled": True, "url": "https://hooks.example.invalid/wh1"}})
    result = alerts.notify_security(_security(blocked=False, risk=0.6), config=cfg)
    assert result["sent"] is True


def test_send_webhook_uses_urllib(monkeypatch):
    calls = []

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"{}"

    def _fake_urlopen(req, timeout=0):
        calls.append((req.full_url, req.data))
        return _FakeResponse()

    monkeypatch.setattr(alerts.urllib.request, "urlopen", _fake_urlopen)
    ok = alerts._send_webhook("https://hooks.example.invalid/wh1", {"a": 1})
    assert ok is True
    assert calls[0][0] == "https://hooks.example.invalid/wh1"


def test_send_webhook_fails_soft_on_network_error(monkeypatch):
    def _boom(req, timeout=0):
        raise OSError("no network")

    monkeypatch.setattr(alerts.urllib.request, "urlopen", _boom)
    ok = alerts._send_webhook("https://hooks.example.invalid/wh1", {"a": 1})
    assert ok is False


def test_send_slack_posts_text_payload(monkeypatch):
    captured = {}

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"ok"

    def _fake_urlopen(req, timeout=0):
        captured["data"] = req.data
        return _FakeResponse()

    monkeypatch.setattr(alerts.urllib.request, "urlopen", _fake_urlopen)
    ok = alerts._send_slack("https://hooks.example.invalid/wh2", "hello")
    assert ok is True
    import json as _json
    assert _json.loads(captured["data"])["text"] == "hello"


def test_send_email_fails_soft_without_smtp_config():
    ok = alerts._send_email({}, subject="s", body="b")
    assert ok is False


def test_send_email_uses_smtplib(monkeypatch):
    sent = {}

    class _FakeSMTP:
        def __init__(self, host, port, timeout=10):
            sent["host"] = host
            sent["port"] = port

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self):
            sent["tls"] = True

        def login(self, user, pwd):
            sent["login"] = (user, pwd)

        def send_message(self, msg):
            sent["sent"] = True

    monkeypatch.setattr(alerts.smtplib, "SMTP", _FakeSMTP)
    smtp_cfg = {"smtp_host": "smtp.example.invalid", "smtp_port": 587, "use_tls": True,
               "username": "u"}
    smtp_cfg["password"] = "p"
    smtp_cfg["from_addr"] = "alerts-noreply"
    smtp_cfg["to_addrs"] = ["compliance-inbox"]
    ok = alerts._send_email(smtp_cfg, subject="Budget alert", body="over threshold")
    assert ok is True
    assert sent["sent"] is True
    assert sent["tls"] is True


def test_env_overrides_webhook_url(monkeypatch):
    monkeypatch.setenv("PROMPTWISE_ALERT_WEBHOOK_URL", "https://from-env.example.invalid/wh3")
    cfg = alerts.AlertConfig(enabled=True, channels={"webhook": {"enabled": True, "url": ""}})
    url = alerts._resolve_webhook_url(cfg)
    assert url == "https://from-env.example.invalid/wh3"


def test_notify_budget_never_raises_on_send_error(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(alerts, "_send_webhook", _boom)
    cfg = alerts.AlertConfig(enabled=True, budget_min_level="warn",
                             channels={"webhook": {"enabled": True, "url": "https://hooks.example.invalid/wh1"}})
    result = alerts.notify_budget(_budget(alert_level="critical"), config=cfg)
    assert result["sent"] is False
    assert "error" in result
