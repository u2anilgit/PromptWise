from promptwise.core.model_sources import CliModelSource, LocalOverrideSource


def test_cli_source_unavailable_when_binary_missing():
    src = CliModelSource(key="fakecli", command=["definitely-not-a-real-binary-xyz", "--models"],
                         pattern=r"(?P<alias>\S+)", family_map={})
    assert src.available() is False
    assert src.fetch() == []


def test_cli_source_parses_stdout_with_named_groups():
    stdout = "gizmo-3  2026-09-01\ngizmo-2  2026-04-01\n"
    src = CliModelSource(
        key="gizmo", command=["gizmo", "--models"],
        pattern=r"^(?P<alias>gizmo-\d+)\s+(?P<release_date>\d{4}-\d{2}-\d{2})$",
        family_map={"gizmo": {"family": "gizmo-fam", "provider": "gizmo", "tier": "balanced"}},
        runner=lambda cmd, timeout: stdout)
    recs = sorted(src.fetch(), key=lambda r: r.alias)
    assert [r.alias for r in recs] == ["gizmo-2", "gizmo-3"]
    assert recs[0].family == "gizmo-fam"
    assert recs[0].provider == "gizmo"
    assert recs[1].release_date == "2026-09-01"
    assert recs[0].source == "gizmo"


def test_longest_family_map_prefix_wins():
    src = CliModelSource(
        key="gizmo", command=["gizmo"], pattern=r"^(?P<alias>\S+)$",
        family_map={
            "gizmo": {"family": "generic", "provider": "gizmo", "tier": "fast"},
            "gizmo-pro": {"family": "pro", "provider": "gizmo", "tier": "powerful"},
        },
        runner=lambda cmd, timeout: "gizmo-pro-1\ngizmo-lite-1\n")
    got = {r.alias: (r.family, r.tier) for r in src.fetch()}
    assert got["gizmo-pro-1"] == ("pro", "powerful")
    assert got["gizmo-lite-1"] == ("generic", "fast")


def test_cli_source_runner_failure_fails_open():
    def boom(cmd, timeout):
        raise OSError("no such binary")
    src = CliModelSource(key="gizmo", command=["gizmo"], pattern=r"(?P<alias>\S+)",
                         family_map={}, runner=boom)
    assert src.fetch() == []


def test_cli_source_deduplicates_repeated_aliases():
    src = CliModelSource(key="g", command=["g"], pattern=r"^(?P<alias>\S+)$",
                         family_map={}, runner=lambda c, t: "a\na\nb\n")
    assert sorted(r.alias for r in src.fetch()) == ["a", "b"]


def test_local_override_has_highest_priority_and_is_absent_by_default(tmp_path):
    src = LocalOverrideSource(path=tmp_path / "model_catalog.local.yaml")
    assert src.key == "local"
    assert src.priority == 40
    assert src.available() is False
    assert src.fetch() == []


def test_local_override_reads_a_user_catalog(tmp_path):
    p = tmp_path / "model_catalog.local.yaml"
    p.write_text(
        "families:\n  mine: {provider: me, tier: fast}\n"
        "models:\n  - alias: my-model\n    family: mine\n", encoding="utf-8")
    src = LocalOverrideSource(path=p)
    assert src.available() is True
    recs = src.fetch()
    assert [r.alias for r in recs] == ["my-model"]
    assert recs[0].source == "local"
