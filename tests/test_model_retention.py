from promptwise.core.model_retention import apply_retention


def _m(alias, family, date, status="current"):
    return {"alias": alias, "family": family, "release_date": date, "status": status}


def test_keeps_newest_three_current_and_deprecates_older():
    models = [
        _m("a-1", "fam", "2026-01-01"),
        _m("a-2", "fam", "2026-04-01"),
        _m("a-3", "fam", "2026-07-01"),
        _m("a-4", "fam", "2026-09-01"),
    ]
    apply_retention(models, keep_per_family=3)
    by_alias = {m["alias"]: m["status"] for m in models}
    assert by_alias == {"a-4": "current", "a-3": "current",
                        "a-2": "current", "a-1": "deprecated"}


def test_never_deletes_a_row():
    models = [_m("a-%d" % i, "fam", "2026-0%d-01" % i) for i in range(1, 6)]
    before = {m["alias"] for m in models}
    apply_retention(models, keep_per_family=2)
    assert {m["alias"] for m in models} == before


def test_revives_deprecated_rows_to_meet_the_minimum():
    """A fetch that returned only the newest model leaves everything else
    deprecated. Retention must undo that, or the 'previous generations stay
    resolvable' guarantee lasts exactly one refresh."""
    models = [
        _m("a-3", "fam", "2026-07-01", status="current"),
        _m("a-2", "fam", "2026-04-01", status="deprecated"),
        _m("a-1", "fam", "2026-01-01", status="deprecated"),
    ]
    apply_retention(models, keep_per_family=3)
    assert all(m["status"] == "current" for m in models)


def test_min_keep_floor_beats_a_too_small_keep_per_family():
    models = [
        _m("a-3", "fam", "2026-07-01"),
        _m("a-2", "fam", "2026-04-01"),
        _m("a-1", "fam", "2026-01-01"),
    ]
    apply_retention(models, keep_per_family=1, min_keep=2)
    statuses = {m["alias"]: m["status"] for m in models}
    assert statuses["a-3"] == "current"
    assert statuses["a-2"] == "current"
    assert statuses["a-1"] == "deprecated"


def test_families_are_independent():
    models = [
        _m("a-2", "famA", "2026-07-01"), _m("a-1", "famA", "2026-01-01"),
        _m("b-2", "famB", "2026-07-01"), _m("b-1", "famB", "2026-01-01"),
    ]
    apply_retention(models, keep_per_family=1, min_keep=1)
    statuses = {m["alias"]: m["status"] for m in models}
    assert statuses == {"a-2": "current", "a-1": "deprecated",
                        "b-2": "current", "b-1": "deprecated"}


def test_undated_rows_are_ordered_by_alias_descending():
    """The shipped catalog omits release_date where it could not be verified;
    versioned aliases still have a defensible newest-first order."""
    models = [
        {"alias": "grok-4.3", "family": "g", "status": "current"},
        {"alias": "grok-4.6", "family": "g", "status": "current"},
        {"alias": "grok-4.5", "family": "g", "status": "current"},
    ]
    apply_retention(models, keep_per_family=2, min_keep=2)
    statuses = {m["alias"]: m["status"] for m in models}
    assert statuses == {"grok-4.6": "current", "grok-4.5": "current",
                        "grok-4.3": "deprecated"}


def test_rows_without_a_family_are_left_alone():
    models = [{"alias": "orphan", "status": "current"}]
    apply_retention(models)
    assert models[0]["status"] == "current"


def test_env_override_sets_the_keep_count(monkeypatch):
    from promptwise.core.model_retention import keep_setting
    monkeypatch.setenv("PROMPTWISE_MODEL_KEEP_PER_FAMILY", "5")
    assert keep_setting() == 5
    monkeypatch.setenv("PROMPTWISE_MODEL_KEEP_PER_FAMILY", "1")
    assert keep_setting() == 2, "the min_keep floor must survive a hostile env value"
    monkeypatch.setenv("PROMPTWISE_MODEL_KEEP_PER_FAMILY", "not-a-number")
    assert keep_setting() == 3
