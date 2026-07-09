"""Phase 13.3 — expand OWASP coverage past the original 5 categories.

Adds Cryptographic Failures (A02), Insecure Deserialization (A08), SSRF (A10),
Path Traversal (A01), and debug-mode misconfiguration (A05). The original five
categories and the benign parameterized-query counterexample must be unchanged.
"""
from promptwise.security.scanner import SecurityScanner

S = SecurityScanner()


def _cats(code):
    return {v["category"] for v in S.check_owasp(code)}


def test_weak_hash_flagged():
    cats = _cats("import hashlib\ndigest = hashlib.md5(data).hexdigest()")
    assert any("Cryptographic" in c for c in cats)


def test_weak_cipher_flagged():
    cats = _cats("from Crypto.Cipher import DES\ncipher = DES.new(key)")
    assert any("Cryptographic" in c for c in cats)


def test_insecure_deserialization_flagged():
    cats = _cats("import pickle\nobj = pickle.loads(blob)")
    assert any("Integrity" in c or "Deserial" in c for c in cats)


def test_unsafe_yaml_load_flagged_but_safe_load_clean():
    assert any("Integrity" in c or "Deserial" in c for c in _cats("cfg = yaml.load(stream)"))
    assert _cats("cfg = yaml.safe_load(stream)") == set()


def test_ssrf_flagged_on_variable_url():
    cats = _cats("import requests\nr = requests.get(target_url)")
    assert any("SSRF" in c for c in cats)


def test_ssrf_not_flagged_on_literal_url():
    assert not any("SSRF" in c for c in _cats("r = requests.get('https://api.example.com/health')"))


def test_path_traversal_flagged():
    cats = _cats("with open('../../' + user_supplied) as f:\n    body = f.read()")
    assert any("Access Control" in c or "Traversal" in c for c in cats)


def test_debug_mode_flagged():
    cats = _cats("app.run(debug=True)")
    assert any("Misconfiguration" in c for c in cats)


def test_original_categories_and_benign_unchanged():
    # Original SQLi detection still fires...
    assert any("SQL Injection" in c for c in _cats('cursor.execute(f"SELECT * FROM t WHERE id={x}")'))
    # ...and the parameterized-query benign counterexample stays clean.
    assert _cats('cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))') == set()
