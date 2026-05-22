"""In-process cache of the curated scheme corpus.

The JSON files under /scheme-corpus/schemes/processed/*.json are the
single source of truth for eligibility_rules at runtime. Loaded once on
import and refreshed by reload() if needed.
"""
import json
import threading
from pathlib import Path

CORPUS_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "scheme-corpus"
    / "schemes"
    / "processed"
)

_lock = threading.Lock()
_cache: dict[str, dict] = {}


def _load_all() -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not CORPUS_DIR.exists():
        return out
    for path in sorted(CORPUS_DIR.glob("*.json")):
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        out[data["scheme_id"]] = data
    return out


def reload() -> None:
    with _lock:
        _cache.clear()
        _cache.update(_load_all())


def _ensure() -> None:
    if not _cache:
        with _lock:
            if not _cache:
                _cache.update(_load_all())


def get_scheme(scheme_id: str) -> dict | None:
    _ensure()
    return _cache.get(scheme_id)


def all_schemes() -> list[dict]:
    _ensure()
    return list(_cache.values())


def eligibility_rules(scheme_id: str) -> dict:
    scheme = get_scheme(scheme_id)
    if not scheme:
        return {"requires_external_verification": False, "rules": []}
    return scheme.get("eligibility_rules", {"requires_external_verification": False, "rules": []})
