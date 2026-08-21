"""End-to-end acceptance check from the WP4 design spec: import the seed
pack, correlate a finding that references a seeded indicator, and confirm
create_incident auto-tags with the matching incident's context."""
import json
from pathlib import Path

import pytest

import promptwise.server  # noqa: F401 -- collection-order guard, see WP1 Task 6 / WP2 Tasks 3/5/7/9 / WP4 Tasks 6/8 for the bug this guards against

from promptwise.security.threat_intel import ThreatIntelStore, import_bundle_file, correlate

SEED_PATH = Path(__file__).parent.parent / "corpus" / "threat_intel_seed.json"


def test_seed_pack_imports_and_correlates(tmp_path):
    store = ThreatIntelStore(db_path=tmp_path / "intel.db")
    result = import_bundle_file(str(SEED_PATH), source="seed", store=store)
    assert result["imported"] > 0

    # a WP2-style finding mentioning the Shai-Hulud worm package name
    matches = correlate(store, content="postinstall script pulled shai-hulud into node_modules", incident_id=1)
    assert any(m["matched_on"] == "indicator_pattern" for m in matches)


@pytest.mark.asyncio
async def test_create_incident_tags_with_seeded_intel(tmp_path, monkeypatch):
    store = ThreatIntelStore(db_path=tmp_path / "intel.db")
    import_bundle_file(str(SEED_PATH), source="seed", store=store)
    monkeypatch.setattr(
        "promptwise.security.threat_intel.ThreatIntelStore",
        lambda *a, **kw: store)

    from promptwise.core.incidents import IncidentStore
    monkeypatch.setattr(
        "promptwise.core.incidents.IncidentStore",
        lambda *a, **kw: IncidentStore(db_path=tmp_path / "incidents.db"))

    import promptwise.handlers.incidents as incidents_handlers

    class _FakeCtx:
        pass

    out = await incidents_handlers._handle_create_incident(_FakeCtx(), {
        "title": "malicious package detected", "description": "found postmark-mcp in dependency tree",
    })
    result = json.loads(out)
    assert len(result["intel_matches"]) >= 1
