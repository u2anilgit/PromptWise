from promptwise.core.model_sources import ModelRecord, SourceRegistry


class _Stub:
    def __init__(self, key, priority, records, ok=True, boom=False):
        self.key, self.priority = key, priority
        self._records, self._ok, self._boom = records, ok, boom

    def available(self):
        return self._ok

    def fetch(self):
        if self._boom:
            raise RuntimeError("source exploded")
        return self._records


def _rec(alias, **kw):
    kw.setdefault("family", "fam")
    kw.setdefault("provider", "claude")
    kw.setdefault("tier", "balanced")
    return ModelRecord(alias=alias, **kw)


def test_to_registry_row_emits_registry_keys():
    row = _rec("m-1", release_date="2026-09-01", price={"input_per_mtok": 3.0},
               context_window=200000, source="pinned").to_registry_row()
    assert row["alias"] == "m-1"
    assert row["family"] == "fam"
    assert row["status"] == "current"
    assert row["release_date"] == "2026-09-01"
    assert row["price"] == {"input_per_mtok": 3.0}
    assert row["context_window"] == 200000


def test_higher_priority_source_wins_on_alias_conflict():
    reg = SourceRegistry()
    reg.register(_Stub("pinned", 10, [_rec("m-1", release_date="2026-01-01")]))
    reg.register(_Stub("api", 30, [_rec("m-1", release_date="2026-09-01")]))
    out = {r.alias: r for r in reg.fetch_all()}
    assert out["m-1"].release_date == "2026-09-01"
    assert out["m-1"].source == "api"


def test_unavailable_source_is_skipped():
    reg = SourceRegistry()
    reg.register(_Stub("api", 30, [_rec("m-9")], ok=False))
    assert reg.fetch_all() == []


def test_raising_source_never_breaks_the_others():
    reg = SourceRegistry()
    reg.register(_Stub("bad", 30, [], boom=True))
    reg.register(_Stub("pinned", 10, [_rec("m-1")]))
    out = reg.fetch_all()
    assert [r.alias for r in out] == ["m-1"]
    assert any("bad" in e for e in reg.errors)
