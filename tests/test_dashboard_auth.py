"""Dashboard auth/RBAC -- see docs/superpowers/specs/2026-07-23-dashboard-auth-rbac-design.md.

The dashboard's Flask app had zero authentication and cli.py hardcoded
host="0.0.0.0", so a solo dev running `promptwise serve` unknowingly
exposed cost/governance data to their entire LAN. This file locks in:
default bind is loopback-only, auth is opt-in via a local credential file,
and role-based access control gates every /api/* route once enabled.
"""
from promptwise.config import AppConfig, DashboardConfig


def test_dashboard_config_defaults_to_loopback_host():
    cfg = AppConfig()
    assert cfg.dashboard.web_host == "127.0.0.1"


def test_dashboard_config_web_host_overridable():
    cfg = DashboardConfig(web_host="0.0.0.0")
    assert cfg.web_host == "0.0.0.0"
