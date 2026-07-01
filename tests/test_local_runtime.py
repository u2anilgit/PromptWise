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
