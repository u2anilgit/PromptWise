"""Phase 6 WP8 — local-model runtime: device config, discovery, long-output split."""
from promptwise.core import local_runtime as L


# ── device probe + token config ──────────────────────────────────────────────
def test_probe_device_shape():
    d = L.probe_device()
    assert "cores" in d and d["cores"] >= 1
    assert "ram_gb" in d and "vram_gb" in d and "platform" in d


def test_token_config_uses_vram_when_known():
    cfg = L.recommend_token_config({"vram_gb": 24, "ram_gb": 64}, model_ctx=32768)
    assert cfg["basis"] == "vram"
    assert 2048 <= cfg["num_ctx"] <= 32768
    assert cfg["max_output_tokens"] <= cfg["num_ctx"]


def test_token_config_conservative_without_vram():
    cfg = L.recommend_token_config({"vram_gb": None, "ram_gb": None}, model_ctx=8192)
    assert cfg["basis"] == "conservative-default"
    assert cfg["num_ctx"] <= 4096


def test_token_config_ram_fallback():
    cfg = L.recommend_token_config({"vram_gb": None, "ram_gb": 16}, model_ctx=8192)
    assert cfg["basis"] == "ram"


# ── discovery (injected http) ────────────────────────────────────────────────
def test_discover_ollama_parses_models():
    def fake_get(url):
        assert url.endswith("/api/tags")
        return {"models": [{"name": "llama3:8b", "size": 8_000_000_000},
                           {"name": "qwen2:0.5b", "size": 500_000_000}]}
    models = L.discover_ollama(http_get=fake_get)
    assert [m["alias"] for m in models] == ["llama3:8b", "qwen2:0.5b"]


def test_discover_ollama_failsoft_on_error():
    def boom(url):
        raise ConnectionError("no daemon")
    assert L.discover_ollama(http_get=boom) == []


def test_to_registry_rows_tiers_by_size():
    rows = L.to_registry_rows([{"alias": "big", "size": 30e9}, {"alias": "small", "size": 1e9}])
    by = {r["alias"]: r for r in rows}
    assert by["big"]["tier"] == "powerful" and by["small"]["tier"] == "fast"
    assert all(r["family"] == "local" and r["price"]["input_per_mtok"] == 0.0 for r in rows)


# ── discovery -> registry auto-population ────────────────────────────────────
def _seed_registry(tmp_path):
    reg = tmp_path / "models.yaml"
    reg.write_text(
        "schema_version: 1\n"
        "families:\n  claude-opus: { provider: claude, tier: powerful }\n"
        "models:\n  - { alias: claude-opus-4-8, family: claude-opus, status: current, release_date: \"2026-06-01\" }\n",
        encoding="utf-8")
    return reg


def test_populate_local_adds_local_models(tmp_path):
    from promptwise.core.model_registry import ModelRegistry
    reg = _seed_registry(tmp_path)
    get = lambda url: {"models": [{"name": "llama3:8b", "size": 8e9}, {"name": "qwen2:0.5b", "size": 5e8}]}
    out = L.populate_local(registry_path=reg, http_get=get)
    assert out["populated"] is True and out["added"] == 2
    r = ModelRegistry(reg)
    assert "llama3:8b" in r.all_aliases()
    assert r.resolve("fast", "local") in ("llama3:8b", "qwen2:0.5b")
    # cloud family untouched
    assert "claude-opus-4-8" in r.all_aliases() and not r.is_deprecated("claude-opus-4-8")


def test_populate_local_is_idempotent(tmp_path):
    reg = _seed_registry(tmp_path)
    get = lambda url: {"models": [{"name": "llama3:8b", "size": 8e9}]}
    L.populate_local(registry_path=reg, http_get=get)
    again = L.populate_local(registry_path=reg, http_get=get)
    assert again["populated"] is False and again["reason"] == "no change"


def test_populate_local_deprecates_vanished_local_model(tmp_path):
    from promptwise.core.model_registry import ModelRegistry
    reg = _seed_registry(tmp_path)
    L.populate_local(registry_path=reg, http_get=lambda url: {"models": [{"name": "gone:7b", "size": 7e9}]})
    # next discovery no longer lists it -> deprecated, not deleted
    L.populate_local(registry_path=reg, http_get=lambda url: {"models": [{"name": "here:7b", "size": 7e9}]})
    r = ModelRegistry(reg)
    assert r.is_deprecated("gone:7b") and "gone:7b" in r.all_aliases()
    assert not r.is_deprecated("here:7b")


def test_populate_local_noop_when_no_daemon(tmp_path):
    reg = _seed_registry(tmp_path)
    out = L.populate_local(registry_path=reg, http_get=lambda url: {"models": []})
    assert out["populated"] is False and out["reason"] == "no local runtime"


# ── long-output splitting (the hard part) ────────────────────────────────────
def test_short_output_is_single_chunk():
    out = L.split_output("hello world", max_chars=100)
    assert len(out) == 1 and out[0]["kind"] == "single"


def test_split_never_cuts_inside_a_code_fence():
    code = "```python\n" + "x = 1\n" * 40 + "```"
    text = "Intro paragraph.\n\n" + code + "\n\nOutro paragraph."
    chunks = L.split_output(text, max_chars=80)
    # the fenced block must appear intact within exactly one chunk
    joined_codes = [c["text"] for c in chunks if "```python" in c["text"]]
    assert len(joined_codes) == 1
    assert joined_codes[0].count("```") == 2  # opening + closing together


def test_split_prefers_sentence_boundaries():
    text = "First sentence here. Second sentence here. Third sentence here. Fourth one too."
    chunks = L.split_output(text, max_chars=40)
    assert len(chunks) > 1
    # no chunk should end mid-word in the common case
    assert all(not c["text"].endswith(" ") for c in chunks)


def test_oversized_code_fence_kept_whole_and_flagged():
    big_code = "```\n" + "y=2\n" * 200 + "```"
    chunks = L.split_output(big_code, max_chars=50)
    code_chunks = [c for c in chunks if c["kind"] == "code"]
    assert code_chunks and code_chunks[0]["oversized"] is True
    assert code_chunks[0]["text"].count("```") == 2


# ── stitching + continuation ─────────────────────────────────────────────────
def test_stitch_dedupes_overlap():
    a = "The quick brown fox jumps over the lazy dog and runs away fast."
    b = "runs away fast. Then it disappears into the forest quietly today."
    joined = L.stitch([a, b])
    assert joined.count("runs away fast") == 1


def test_stitch_plain_concatenation_when_no_overlap():
    assert L.stitch(["alpha ", "beta"]) == "alpha beta"


def test_continuation_prompt_contains_tail():
    p = L.continuation_prompt("...the final words of the draft", tail_chars=100)
    assert "final words of the draft" in p
    assert "not repeat" in p.lower() or "do not repeat" in p.lower()


# ── live client (injected transport) ─────────────────────────────────────────
def test_ollama_client_builds_generate_body():
    seen = {}

    def post(url, body):
        seen["url"] = url
        seen["body"] = body
        return {"response": "ok", "context": [1, 2, 3], "done": True}

    c = L.OllamaClient(http_post=post)
    out = c.generate("llama3", "hi", num_ctx=4096, context=[9, 9])
    assert seen["url"].endswith("/api/generate")
    assert seen["body"]["model"] == "llama3" and seen["body"]["stream"] is False
    assert seen["body"]["options"]["num_ctx"] == 4096
    assert seen["body"]["context"] == [9, 9]
    assert out["response"] == "ok"


def test_generate_long_uses_context_passthrough():
    posts = []

    def post(url, body):
        posts.append(body)
        if len(posts) == 1:
            return {"response": "Part one ", "context": [1, 2, 3], "done_reason": "length"}
        return {"response": "and part two.", "context": [1, 2, 3, 4], "done_reason": "stop", "done": True}

    out = L.generate_long("llama3", "write a long thing", http_post=post, max_rounds=5)
    assert out["text"] == "Part one and part two."
    assert out["rounds"] == 2
    assert out["incomplete"] is False
    assert out["used_reprime_fallback"] is False
    # the continuation call carried the KV context and an empty prompt (seamless)
    assert posts[1]["context"] == [1, 2, 3]
    assert posts[1]["prompt"] == ""


def test_generate_long_reprime_fallback_without_context():
    posts = []

    def post(url, body):
        posts.append(body)
        if len(posts) == 1:
            return {"response": "chunk A ", "done_reason": "length"}   # no context returned
        return {"response": "chunk B", "done_reason": "stop", "done": True}

    out = L.generate_long("m", "prompt", http_post=post)
    assert out["used_reprime_fallback"] is True
    assert "chunk A" in out["text"] and "chunk B" in out["text"]
    assert "not repeat" in posts[1]["prompt"].lower()


def test_generate_long_failsoft_when_unreachable():
    def post(url, body):
        raise ConnectionError("no daemon")
    out = L.generate_long("m", "prompt", http_post=post)
    assert out["text"] == "" and out["rounds"] >= 1


def test_generate_long_stops_at_max_rounds():
    def post(url, body):
        return {"response": "x", "context": [1], "done_reason": "length"}  # never completes
    out = L.generate_long("m", "prompt", http_post=post, max_rounds=3)
    assert out["rounds"] == 3 and out["incomplete"] is True
