"""Phase 15 — ExactCache: a real, hash-based exact-match result cache.

Extends core/cache_planner.py's pattern from a cost simulator (breakpoint
placement) to something that actually stores and serves results. CachePlanner
itself is untouched; this module lives alongside it.
"""
from promptwise.core.exact_cache import ExactCache, hash_request, normalize_request


def _cache(tmp_path, **kw):
    return ExactCache(tmp_path / "cache.db", **kw)


# ── normalization / hashing ─────────────────────────────────────────────────
def test_whitespace_only_difference_hashes_same():
    a = hash_request("summarize_thread", {"conversation": "hello   world\n\n"})
    b = hash_request("summarize_thread", {"conversation": "  hello world  "})
    assert a == b


def test_dict_key_order_does_not_affect_hash():
    a = hash_request("route_request", {"text": "x", "intent": "code"})
    b = hash_request("route_request", {"intent": "code", "text": "x"})
    assert a == b


def test_distinct_content_hashes_differently():
    a = hash_request("route_request", {"text": "deploy to staging"})
    b = hash_request("route_request", {"text": "deploy to production"})
    assert a != b


def test_case_is_preserved_not_collapsed():
    # Case matters for code/identifiers -- normalization must not lowercase.
    a = hash_request("route_request", {"text": "Deploy"})
    b = hash_request("route_request", {"text": "deploy"})
    assert a != b


def test_different_tool_same_request_hashes_differently():
    a = hash_request("tool_a", {"text": "same"})
    b = hash_request("tool_b", {"text": "same"})
    assert a != b


def test_normalize_request_is_stable_json():
    s1 = normalize_request("t", {"b": 1, "a": 2})
    s2 = normalize_request("t", {"a": 2, "b": 1})
    assert s1 == s2


# ── put / get roundtrip ──────────────────────────────────────────────────────
def test_miss_before_put(tmp_path):
    c = _cache(tmp_path)
    r = c.get("route_request", {"text": "hello"})
    assert r.hit is False
    assert r.value is None


def test_put_then_get_hits_with_same_value(tmp_path):
    c = _cache(tmp_path)
    put = c.put("route_request", {"text": "hello"}, {"tier": "sonnet", "cost": 0.01})
    assert put.stored is True
    got = c.get("route_request", {"text": "hello"})
    assert got.hit is True
    assert got.value == {"tier": "sonnet", "cost": 0.01}


def test_normalized_equivalent_request_still_hits(tmp_path):
    c = _cache(tmp_path)
    c.put("route_request", {"text": "hello   world"}, {"tier": "haiku"})
    got = c.get("route_request", {"text": "  hello world  "})
    assert got.hit is True
    assert got.value == {"tier": "haiku"}


def test_distinct_request_is_a_miss(tmp_path):
    c = _cache(tmp_path)
    c.put("route_request", {"text": "hello"}, {"tier": "sonnet"})
    got = c.get("route_request", {"text": "goodbye"})
    assert got.hit is False


def test_put_overwrites_existing_entry(tmp_path):
    c = _cache(tmp_path)
    c.put("route_request", {"text": "hello"}, {"tier": "haiku"})
    c.put("route_request", {"text": "hello"}, {"tier": "opus"})
    got = c.get("route_request", {"text": "hello"})
    assert got.value == {"tier": "opus"}


# ── TTL expiry ────────────────────────────────────────────────────────────
def test_default_ttl_is_respected(tmp_path):
    c = _cache(tmp_path, default_ttl_seconds=100)
    now = 1_000_000.0
    c.put("route_request", {"text": "hello"}, {"tier": "sonnet"}, ts=now)
    still_fresh = c.get("route_request", {"text": "hello"}, ts=now + 50)
    assert still_fresh.hit is True
    expired = c.get("route_request", {"text": "hello"}, ts=now + 200)
    assert expired.hit is False


def test_expired_entry_is_purged_on_get(tmp_path):
    c = _cache(tmp_path, default_ttl_seconds=10)
    now = 2_000_000.0
    c.put("route_request", {"text": "x"}, {"v": 1}, ts=now)
    c.get("route_request", {"text": "x"}, ts=now + 100)  # triggers expiry + delete
    stats = c.stats()
    assert stats["entries"] == 0


def test_ttl_zero_means_no_expiry(tmp_path):
    c = _cache(tmp_path)
    now = 3_000_000.0
    c.put("route_request", {"text": "stable fact"}, {"v": 1}, ttl_seconds=0, ts=now)
    far_future = c.get("route_request", {"text": "stable fact"}, ts=now + 10_000_000)
    assert far_future.hit is True


def test_custom_ttl_overrides_default(tmp_path):
    c = _cache(tmp_path, default_ttl_seconds=10_000)
    now = 4_000_000.0
    c.put("route_request", {"text": "y"}, {"v": 1}, ttl_seconds=5, ts=now)
    got = c.get("route_request", {"text": "y"}, ts=now + 6)
    assert got.hit is False


# ── hit/miss tracking + stats ────────────────────────────────────────────────
def test_stats_tracks_hits_and_misses(tmp_path):
    c = _cache(tmp_path)
    c.put("route_request", {"text": "a"}, {"v": 1})
    c.get("route_request", {"text": "a"})  # hit
    c.get("route_request", {"text": "a"})  # hit
    c.get("route_request", {"text": "b"})  # miss
    stats = c.stats()
    assert stats["hits"] == 2
    assert stats["misses"] == 1
    assert stats["entries"] == 1
    assert stats["hit_rate"] == round(2 / 3, 4)


def test_stats_empty_cache(tmp_path):
    c = _cache(tmp_path)
    stats = c.stats()
    assert stats == {"entries": 0, "hits": 0, "misses": 0, "hit_rate": 0.0, "by_category": {}}


def test_stats_by_category(tmp_path):
    c = _cache(tmp_path)
    c.put("route_request", {"text": "a"}, {"v": 1}, category="routing")
    c.put("route_request", {"text": "b"}, {"v": 1}, category="routing")
    c.put("security_check", {"text": "c"}, {"v": 1}, category="security")
    stats = c.stats()
    assert stats["by_category"] == {"routing": 2, "security": 1}


def test_get_result_reports_age_and_expiry(tmp_path):
    c = _cache(tmp_path, default_ttl_seconds=100)
    now = 5_000_000.0
    c.put("route_request", {"text": "a"}, {"v": 1}, ts=now)
    got = c.get("route_request", {"text": "a"}, ts=now + 10)
    assert got.age_seconds == 10
    assert got.expires_in_seconds == 90


# ── purge / clear ────────────────────────────────────────────────────────────
def test_purge_expired_removes_only_expired(tmp_path):
    c = _cache(tmp_path, default_ttl_seconds=10)
    now = 6_000_000.0
    c.put("route_request", {"text": "old"}, {"v": 1}, ts=now)
    c.put("route_request", {"text": "new"}, {"v": 1}, ts=now, ttl_seconds=1000)
    removed = c.purge_expired(ts=now + 100)
    assert removed == 1
    assert c.stats()["entries"] == 1


def test_clear_empties_the_cache(tmp_path):
    c = _cache(tmp_path)
    c.put("route_request", {"text": "a"}, {"v": 1})
    c.clear()
    assert c.stats()["entries"] == 0


# ── category exclusion (never-cache) ─────────────────────────────────────────
def test_medical_category_is_never_cached(tmp_path):
    c = _cache(tmp_path)
    put = c.put("some_tool", {"text": "your dosage"}, {"advice": "..."}, category="medical")
    assert put.stored is False
    assert "medical" in put.reason
    assert c.get("some_tool", {"text": "your dosage"}).hit is False


def test_category_substring_match_blocks(tmp_path):
    c = _cache(tmp_path)
    put = c.put("some_tool", {"text": "x"}, {"v": 1}, category="medical_diagnosis")
    assert put.stored is False


def test_ordinary_category_is_cached(tmp_path):
    c = _cache(tmp_path)
    put = c.put("some_tool", {"text": "x"}, {"v": 1}, category="routing")
    assert put.stored is True
