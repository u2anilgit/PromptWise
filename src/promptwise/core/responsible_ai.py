"""responsible_ai — advisory grounding / bias / ethics heuristics.

Local-first and stdlib-only (optional YAML lexicon override). No model download,
no network, air-gapped safe. This layer answers the three concerns that dominate
responsible-AI discourse — factual grounding, fairness/bias, and ethical
disclosure — without any additional infrastructure.

**Advisory by design.** Every function returns *findings*, never a verdict that
should hard-block a turn. Heuristic bias/ethics signals carry real false-positive
rates; auto-blocking on them would be its own harm (silent censorship, broken
trust). Callers surface findings as warnings; only high-precision deterministic
signals elsewhere (secrets, destructive shell) ever block.
"""
from __future__ import annotations

import re
from pathlib import Path

# ── tunable lexicon (config override, safe in-code fallback) ─────────────────
_DEFAULT_GROUP_TERMS = [
    "women", "men", "girls", "boys", "immigrants", "foreigners", "muslims",
    "christians", "jews", "hindus", "buddhists", "atheists", "asians",
    "africans", "americans", "europeans", "blacks", "whites", "latinos",
    "elderly", "millennials", "boomers", "teenagers", "disabled people",
    "poor people", "rich people", "liberals", "conservatives",
]
_DEFAULT_ADVICE_DOMAINS = {
    "medical": ["diagnos", "symptom", "dosage", "medication", "prescription",
                "treatment", "cure", "disease", "mg of", "milligram"],
    "legal": ["lawsuit", "liable", "legally", "contract clause", "sue ",
              "prosecut", "plead", "statute", "court will"],
    "financial": ["invest", "stock", "portfolio", "guaranteed return",
                  "buy shares", "sell shares", "crypto", "retirement fund"],
}
_DISCLAIMER_TOKENS = [
    "consult", "professional", "not financial advice", "not legal advice",
    "not medical advice", "seek advice", "disclaimer", "for informational",
    "qualified", "your own research", "may vary",
]
_OVERCONFIDENCE = [
    "guaranteed", "100% safe", "risk-free", "risk free", "always works",
    "will definitely", "no side effects", "completely safe", "never fails",
    "certain to", "impossible to fail",
]
_ATTRIBUTION_NO_SOURCE = [
    "studies show", "research shows", "experts say", "it is well known",
    "it's well known", "scientists agree", "everyone knows", "proven that",
]


def _load_lexicon() -> dict:
    """Overlay config/responsible_ai.yaml onto the defaults, if present."""
    lex = {
        "group_terms": list(_DEFAULT_GROUP_TERMS),
        "advice_domains": {k: list(v) for k, v in _DEFAULT_ADVICE_DOMAINS.items()},
        "disclaimer_tokens": list(_DISCLAIMER_TOKENS),
        "overconfidence": list(_OVERCONFIDENCE),
        "attribution_no_source": list(_ATTRIBUTION_NO_SOURCE),
        "harm_categories": [],
    }
    try:
        import yaml
        for p in (Path("config") / "responsible_ai.yaml",
                  Path(__file__).resolve().parents[3] / "config" / "responsible_ai.yaml"):
            if p.exists():
                data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                for key, val in data.items():
                    if isinstance(val, list):
                        lex[key] = val
                    elif isinstance(val, dict):
                        lex[key] = val
                break
    except Exception:
        pass  # defaults are sufficient; never fail
    return lex


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def _content_words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-zA-Z]{4,}", s.lower())}


# ── grounding ────────────────────────────────────────────────────────────────
def check_grounding(response: str, sources: str | list[str] | None = None) -> dict:
    """Flag claim-like sentences unsupported by the provided sources, plus
    fabrication markers (unbacked attributions, bare citation refs, DOIs).

    Without sources, sentence-level grounding is *not applicable* (a false
    "hallucination" flag on ungrounded prompts would be worse than none); only
    context-free fabrication markers are reported.
    """
    findings: list[dict] = []
    text = response or ""
    if not text.strip():
        return {"applicable": False, "score": 1.0, "findings": findings}

    low = text.lower()
    for phrase in _ATTRIBUTION_NO_SOURCE:
        if phrase in low:
            findings.append({"check": "grounding", "severity": "medium",
                             "detail": f"unbacked attribution: '{phrase}'", "span": phrase})
    # bare numeric citation refs with no bibliography line
    if re.search(r"\[\d{1,3}\]", text) and not re.search(r"(?im)^\s*(references|bibliography)\b", text):
        findings.append({"check": "grounding", "severity": "low",
                         "detail": "citation marker(s) with no reference list", "span": "[n]"})
    for doi in re.findall(r"10\.\d{4,9}/\S+", text)[:3]:
        findings.append({"check": "grounding", "severity": "low",
                         "detail": "DOI-style reference — verify it exists", "span": doi})

    src_join = " ".join(sources) if isinstance(sources, list) else (sources or "")
    if src_join.strip():
        src_tokens = _content_words(src_join)
        claim_like = re.compile(r"\d|\bpercent\b|%|\[\d+\]")
        unsupported = 0
        checked = 0
        for sent in _sentences(text):
            if not claim_like.search(sent):
                continue
            checked += 1
            words = _content_words(sent)
            if not words:
                continue
            overlap = len(words & src_tokens) / len(words)
            if overlap < 0.2:
                unsupported += 1
                findings.append({"check": "grounding", "severity": "high",
                                 "detail": "claim not supported by provided sources",
                                 "span": sent[:160]})
        score = 1.0 if not checked else max(0.0, 1.0 - unsupported / checked)
        return {"applicable": True, "score": round(score, 3), "findings": findings}

    return {"applicable": False, "score": 1.0, "findings": findings}


# ── bias ───────────────────────────────────────────────────────────────────
def check_bias(text: str, lexicon: dict | None = None) -> dict:
    """Flag sweeping generalizations over a group (not mere mention). Advisory."""
    findings: list[dict] = []
    if not (text or "").strip():
        return {"findings": findings}
    lex = lexicon or _load_lexicon()
    groups = "|".join(re.escape(g) for g in lex.get("group_terms", []))
    if not groups:
        return {"findings": findings}
    low = text.lower()
    # "all/every/no/most <group>" and "<group> are always/never ..."
    pat_pre = re.compile(rf"\b(all|every|no|none of the|most|typical)\s+({groups})\b")
    pat_post = re.compile(rf"\b({groups})\s+(are|is|always|never|can't|cannot|tend to be)\b")
    for m in list(pat_pre.finditer(low))[:10]:
        findings.append({"check": "bias", "severity": "medium",
                         "detail": "sweeping generalization over a group",
                         "span": low[max(0, m.start()): m.start() + 60].strip()})
    for m in list(pat_post.finditer(low))[:10]:
        findings.append({"check": "bias", "severity": "low",
                         "detail": "group-level absolute statement",
                         "span": low[max(0, m.start()): m.start() + 60].strip()})
    return {"findings": findings}


# ── ethics ─────────────────────────────────────────────────────────────────
def check_ethics(text: str, action: str = "", lexicon: dict | None = None) -> dict:
    """Flag advice given without disclosure, overconfident absolutes, and any
    configured harm categories. Advisory."""
    findings: list[dict] = []
    if not (text or "").strip():
        return {"findings": findings}
    lex = lexicon or _load_lexicon()
    low = text.lower()

    has_disclaimer = any(tok in low for tok in lex.get("disclaimer_tokens", []))
    for domain, kws in (lex.get("advice_domains") or {}).items():
        if any(k in low for k in kws) and not has_disclaimer:
            findings.append({"check": "ethics", "severity": "medium",
                             "detail": f"{domain} advice without a disclosure/disclaimer",
                             "span": domain})
    for tok in lex.get("overconfidence", []):
        if tok in low:
            findings.append({"check": "ethics", "severity": "low",
                             "detail": f"overconfident claim: '{tok}'", "span": tok})
    for harm in lex.get("harm_categories", []):
        term = harm if isinstance(harm, str) else str(harm)
        if term and term.lower() in low:
            findings.append({"check": "ethics", "severity": "high",
                             "detail": f"configured harm category: '{term}'", "span": term})
    return {"findings": findings}


# ── aggregate ────────────────────────────────────────────────────────────────
def scan(response: str, sources: str | list[str] | None = None, action: str = "") -> dict:
    """Run all three advisory checks and merge findings. Never raises."""
    lex = _load_lexicon()
    findings: list[dict] = []
    try:
        g = check_grounding(response, sources)
        findings += g.get("findings", [])
    except Exception:
        g = {"applicable": False, "score": 1.0}
    try:
        findings += check_bias(response, lex).get("findings", [])
    except Exception:
        pass
    try:
        findings += check_ethics(response, action, lex).get("findings", [])
    except Exception:
        pass
    highest = "none"
    order = {"none": 0, "low": 1, "medium": 2, "high": 3}
    for f in findings:
        if order.get(f.get("severity", "low"), 1) > order[highest]:
            highest = f.get("severity", "low")
    return {
        "overall": "review" if findings else "clean",
        "highest_severity": highest,
        "grounding_score": g.get("score", 1.0),
        "grounding_applicable": g.get("applicable", False),
        "findings": findings,
    }
