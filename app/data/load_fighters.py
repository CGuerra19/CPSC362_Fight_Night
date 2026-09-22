"""Data-access layer for the fighter database (FNA-9).

Everything above this module talks to fighters through these functions only.
Nothing else in the app should open fighters.json directly. Storage choice is swappable:
moving to SQLite later means rewriting this file
and nothing else. (in the air option)
"""

import json
import threading
from pathlib import Path

DATA_PATH = Path(__file__).parent / "fighters.json"

# Loaded once on first use and kept in memory. The roster is small enough
# (hundreds of fighters at most) that a dict lookup beats a database query,
# so there is no reason to re-read the file per request.
_cache = None
_lock = threading.Lock()


def _load():
    """Read and index the JSON file. Called once, then cached."""
    global _cache
    with _lock:
        if _cache is not None:
            return _cache

        with open(DATA_PATH, encoding="utf-8") as f:
            raw = json.load(f)

        fighters = raw["fighters"]
        _cache = {
            "meta": raw.get("_meta", {}),
            "by_id": {f["id"]: f for f in fighters},
            "by_name": {f["name"].lower(): f for f in fighters},
            "all": fighters,
        }
        return _cache


def reload():
    """Drop the cache so the next call re-reads from disk.
    Useful after editing fighters.json without restarting Flask.
    """
    global _cache
    with _lock:
        _cache = None


def all_fighters():
    """Every fighter record, in file order."""
    return _load()["all"]


def get_fighter(fighter_id):
    """Look up one fighter by slug id. Returns None if absent."""
    return _load()["by_id"].get(fighter_id)


def get_fighter_by_name(name):
    """Look up one fighter by exact name, case-insensitive. None if absent."""
    if not name:
        return None
    return _load()["by_name"].get(name.strip().lower())


def search_names(prefix, limit=8):
    """Autocomplete support (FNA-7).
    Matches the prefix against both the fighter's name and nickname. Names
    that start with the prefix rank above names that merely contain it, so
    typing "hol" surfaces Holloway before a mid-word match.
    """
    if not prefix or not prefix.strip():
        return []

    q = prefix.strip().lower()
    starts, contains = [], []

    for f in all_fighters():
        name = f["name"].lower()
        nick = (f.get("nickname") or "").lower()

        if name.startswith(q) or nick.startswith(q):
            starts.append(f)
        elif q in name or (nick and q in nick):
            contains.append(f)

    results = (starts + contains)[:limit]
    return [
        {
            "id": f["id"],
            "name": f["name"],
            "nickname": f.get("nickname"),
            "division": f["division"],
            "ranking": f.get("ranking"),
        }
        for f in results
    ]


def data_status():
    """Metadata block, including the unverified-data warning.
    The eval harness (FNA-30) should refuse to run a scored sweep while
    data_status is still UNVERIFIED_SEED.
    """
    meta = _load()["meta"]
    return {
        "status": meta.get("data_status", "UNKNOWN"),
        "verified": meta.get("data_status") == "VERIFIED",
        "fighter_count": len(all_fighters()),
        "last_updated": meta.get("last_updated"),
        "warning": meta.get("warning"),
    }
