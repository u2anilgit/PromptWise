"""security.threat_intel -- STIX 2.1 minimal-subset parser and storage
(WP4). No `stix2` pip dependency (ground rule #3): this module only ever
reads the handful of fields PromptWise's correlation logic actually uses
from `indicator`/`attack-pattern`/`intrusion-set`/`relationship` objects.
Any other STIX object `type` (`malware`, `campaign`, ...) is skipped, not
errored -- fail-soft, matches the project's detector-failure discipline.
"""
from __future__ import annotations

_SUPPORTED_TYPES = {
    "indicator": "indicators",
    "attack-pattern": "attack_patterns",
    "intrusion-set": "intrusion_sets",
    "relationship": "relationships",
}

_REQUIRED_FIELDS = {
    "indicator": ("id", "pattern"),
    "attack-pattern": ("id", "name"),
    "intrusion-set": ("id", "name"),
    "relationship": ("id", "source_ref", "target_ref", "relationship_type"),
}


def parse_bundle(bundle: dict) -> dict:
    """Parse a STIX 2.1 bundle dict into the four supported object-type
    buckets. Anything malformed or of an unsupported type is skipped, never
    raised -- a partially-bad feed still yields whatever is usable."""
    result: dict = {v: [] for v in _SUPPORTED_TYPES.values()}
    if not isinstance(bundle, dict) or bundle.get("type") != "bundle":
        return result
    for obj in bundle.get("objects", []) or []:
        if not isinstance(obj, dict):
            continue
        obj_type = obj.get("type")
        bucket = _SUPPORTED_TYPES.get(obj_type)
        if bucket is None:
            continue
        required = _REQUIRED_FIELDS[obj_type]
        if not all(obj.get(f) for f in required):
            continue
        result[bucket].append(obj)
    return result
