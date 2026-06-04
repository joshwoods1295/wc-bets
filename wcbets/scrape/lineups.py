"""Fetch today's matches and confirmed lineups from Sofascore."""
from __future__ import annotations
import time
import unicodedata
from datetime import date

try:
    from curl_cffi import requests as _requests
    _IMPERSONATE = "chrome136"
except ImportError:
    import requests as _requests
    _IMPERSONATE = None

BASE = "https://api.sofascore.com/api/v1"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-GB,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.sofascore.com/",
    "Origin": "https://www.sofascore.com",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
}

def _get_cookies() -> dict:
    try:
        import streamlit as st
        return dict(st.secrets.get("sofascore_cookies", {}))
    except Exception:
        return {}


_POS_MAP = {
    "G": "GK", "GK": "GK",
    "D": "DF", "DF": "DF",
    "M": "MF", "MF": "MF",
    "F": "FW", "FW": "FW",
}


def _get(url: str) -> dict:
    try:
        time.sleep(0.2)
        kw = {"impersonate": _IMPERSONATE} if _IMPERSONATE else {}
        r = _requests.get(url, headers=HEADERS, cookies=_get_cookies(), timeout=10, **kw)
        return r.json() if r.status_code == 200 else {}
    except Exception:
        return {}


def normalise(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c)).casefold().strip()


def get_todays_matches() -> list[dict]:
    """Return all football matches today, sorted by start time."""
    today = date.today().strftime("%Y-%m-%d")
    data = _get(f"{BASE}/sport/football/scheduled-events/{today}")
    matches = []
    for e in data.get("events", []):
        matches.append({
            "id": e["id"],
            "home": e["homeTeam"]["name"],
            "away": e["awayTeam"]["name"],
            "tournament": e.get("tournament", {}).get("name", "Unknown"),
            "category": e.get("tournament", {}).get("category", {}).get("name", ""),
            "timestamp": e.get("startTimestamp", 0),
            "status": e.get("status", {}).get("description", "Scheduled"),
            "status_type": e.get("status", {}).get("type", "notstarted"),
        })
    matches.sort(key=lambda x: x["timestamp"])
    return matches


def get_lineup(event_id: int) -> dict:
    """Return confirmed starting lineups for a match.

    Returns {"confirmed": bool, "home": [...], "away": [...]}
    Each player: {name, sofascore_id, position, jersey}
    """
    data = _get(f"{BASE}/event/{event_id}/lineups")
    if not data:
        return {"confirmed": False, "home": [], "away": []}

    confirmed = data.get("confirmed", False)
    result = {"confirmed": confirmed, "home": [], "away": []}

    for side in ("home", "away"):
        side_data = data.get(side, {})
        for entry in side_data.get("players", []):
            # Sofascore uses substitute=False for starters (starter field is None)
            if entry.get("substitute", True):
                continue
            p = entry.get("player", {})
            pos_raw = entry.get("position") or p.get("position") or ""
            pos = _POS_MAP.get(str(pos_raw).upper(), None)
            result[side].append({
                "name": p.get("name", ""),
                "sofascore_id": p.get("id"),
                "position": pos,
                "jersey": entry.get("jerseyNumber"),
            })

    return result


def resolve_lineup_to_db(conn, lineup_players: list[dict]) -> list[dict]:
    """Match lineup player names to DB player records.

    Returns list of player dicts (same shape as matchup_query.players_by_country)
    with per-90 stats attached. Players not found in DB are skipped.
    """
    from wcbets.analysis.normalise import per90_row
    from wcbets.config import STAT_COLUMNS

    _P90_KEYS = [c for c in STAT_COLUMNS if c != "minutes"]

    # Build name index from DB
    name_index: dict[str, list] = {}
    for pid, nm in conn.execute("SELECT player_id, name FROM players"):
        name_index.setdefault(normalise(nm), []).append(pid)

    def find_pid(name: str) -> str | None:
        key = normalise(name)
        hits = name_index.get(key, [])
        if not hits:
            qtoks = key.split()
            if len(qtoks) >= 2:
                for db_key, pids in name_index.items():
                    ctoks = db_key.split()
                    if (len(qtoks) <= len(ctoks)
                            and all(q == c for q, c in zip(qtoks, ctoks))):
                        hits.extend(pids)
        return hits[0] if len(hits) >= 1 else None

    cols = ["player_id", "name", "position"] + STAT_COLUMNS
    stat_sql = (
        f"SELECT p.player_id, p.name, p.position, "
        f"{', '.join('s.' + c for c in STAT_COLUMNS)} "
        f"FROM players p JOIN player_stats s ON s.player_id=p.player_id "
        f"WHERE p.player_id=?"
    )

    resolved = []
    for lp in lineup_players:
        pid = find_pid(lp["name"])
        if not pid:
            continue
        row = conn.execute(stat_sql, (pid,)).fetchone()
        if not row:
            continue
        d = dict(zip(cols, row))
        # Override position with lineup position if DB has none
        if lp.get("position") and not d.get("position"):
            d["position"] = lp["position"]
        elif lp.get("position"):
            d["position"] = lp["position"]  # lineup position is more reliable
        resolved.append(per90_row(d, _P90_KEYS))

    return resolved
