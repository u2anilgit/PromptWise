import json

import pytest

from promptwise.core import tool_profiles


class _T:
    def __init__(self, name):
        self.name = name


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.delenv("PROMPTWISE_TOOL_PROFILE", raising=False)
    tool_profiles.set_active_profile("")
    tool_profiles.reset_cache()
    yield
    tool_profiles.set_active_profile("")
    tool_profiles.reset_cache()


def test_default_profile_is_standard():
    assert tool_profiles.active_profile() == "standard"


def test_env_selects_the_profile(monkeypatch):
    monkeypatch.setenv("PROMPTWISE_TOOL_PROFILE", "core")
    assert tool_profiles.active_profile() == "core"


def test_unknown_profile_falls_back_to_full_not_empty(monkeypatch):
    """A typo in the profile name must never silently hide every tool -- an
    empty tool list looks to a host exactly like a broken server."""
    monkeypatch.setenv("PROMPTWISE_TOOL_PROFILE", "typo-here")
    tools = [_T("route_request"), _T("export_audit")]
    assert len(tool_profiles.filter_tools(tools)) == 2


def test_full_profile_returns_everything(monkeypatch):
    monkeypatch.setenv("PROMPTWISE_TOOL_PROFILE", "full")
    tools = [_T("a"), _T("b"), _T("c")]
    assert tool_profiles.filter_tools(tools) == tools


def test_core_profile_is_a_strict_subset_of_standard():
    core = set(tool_profiles.profile_members("core"))
    standard = set(tool_profiles.profile_members("standard"))
    assert core and standard
    assert core < standard


def test_every_profile_member_is_a_real_registered_tool():
    """A profile listing a tool that does not exist silently hides nothing and
    misleads the next editor into thinking it is covered."""
    import promptwise.server as s
    registered = {t.name for t in s._TOOL_DEFS}
    for profile in ("core", "standard"):
        for name in tool_profiles.profile_members(profile):
            assert name in registered, "%s lists unknown tool %s" % (profile, name)


def test_set_active_profile_switches_and_is_reversible():
    tool_profiles.set_active_profile("core")
    assert tool_profiles.active_profile() == "core"
    tool_profiles.set_active_profile("full")
    assert tool_profiles.active_profile() == "full"


def test_core_profile_stays_small():
    import promptwise.server as s
    assert len(tool_profiles.filter_tools(s._TOOL_DEFS, profile="core")) <= 25


def test_standard_is_materially_cheaper_than_full():
    """The whole point is the token saving; a profile that saves nothing is
    complexity for free."""
    import promptwise.server as s

    def size(tools):
        return sum(len(json.dumps({"name": t.name, "description": t.description,
                                   "inputSchema": t.inputSchema})) for t in tools)

    full = size(s._TOOL_DEFS)
    standard = size(tool_profiles.filter_tools(s._TOOL_DEFS, profile="standard"))
    assert standard < full * 0.6, "standard is %d/%d bytes of full" % (standard, full)


def test_a_cyclic_extends_chain_does_not_hang(monkeypatch):
    monkeypatch.setattr(tool_profiles, "_CACHE", {
        "a": {"extends": "b", "tools": ["x"]},
        "b": {"extends": "a", "tools": ["y"]},
    })
    assert sorted(tool_profiles.profile_members("a")) == ["x", "y"]


@pytest.mark.asyncio
async def test_expand_tool_surface_reveals_the_full_listing(monkeypatch):
    import promptwise.server as s
    from promptwise.handlers.detection import _handle_expand_tool_surface

    monkeypatch.setenv("PROMPTWISE_TOOL_PROFILE", "core")
    assert len(await s.list_tools()) <= 25
    out = json.loads(await _handle_expand_tool_surface(None, {"profile": "full"}))
    assert out["active_profile"] == "full"
    assert len(await s.list_tools()) == len(s._TOOL_DEFS)


@pytest.mark.asyncio
async def test_a_hidden_tool_is_still_callable(monkeypatch):
    """Profiles shrink the advertised listing only. A tool that is hidden but
    uncallable would be a regression, not an optimization."""
    import promptwise.server as s

    monkeypatch.setenv("PROMPTWISE_TOOL_PROFILE", "core")
    listed = {t.name for t in await s.list_tools()}
    assert "get_sbom" not in listed
    ctx = await s._build_context()
    result = await s.call_tool(ctx, "get_sbom", {})
    assert "Unknown tool" not in result
