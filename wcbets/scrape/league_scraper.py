"""Scrape player season stats from FBref for configured leagues.

FBref returns each stat group as a separate table with MultiIndex columns
(top-level group, leaf stat). The stats we need are spread across several
tables, and some leaf names collide across groups (e.g. ``Gls`` lives under
both ``Performance`` and ``Per 90 Minutes``). We always want SEASON TOTALS,
never the per-90 variants, so the extraction explicitly excludes the
``Per 90 Minutes`` group.

``map_fbref_row`` is a pure, unit-tested helper that maps ONE flat FBref-shaped
record (simple string keys) to our flat player+stats dict. The live
``scrape_league`` uses the MultiIndex merge path, which is the source of truth
for season totals.
"""
from __future__ import annotations

import pandas as pd

from wcbets.config import LEAGUES, SEASON, STAT_COLUMNS
from wcbets.db import repository as repo

# Canonical stat name -> the FBref leaf column it is read from.
FBREF_MAP = {
    "minutes": "Min", "shots": "Sh", "shots_on_target": "SoT",
    "goals": "Gls", "assists": "Ast", "fouls": "Fls", "fouls_drawn": "Fld",
    "yellows": "CrdY", "reds": "CrdR", "offsides": "Off",
    "tackles": "Tkl", "corners_taken": "CK", "saves": "Saves",
}

# Which leaf column in each stat_type table maps to which canonical stat.
# soccerdata 1.9 supports: standard, keeper, shooting, playing_time, misc.
# tackles (defense table) and corners_taken (passing_types) are not exposed
# in this version and will be stored as 0.
STAT_TABLES = {
    "standard": {"Gls": "goals", "Ast": "assists", "CrdY": "yellows",
                 "CrdR": "reds", "Min": "minutes"},
    "shooting": {"Sh": "shots", "SoT": "shots_on_target"},
    "misc": {"Fls": "fouls", "Fld": "fouls_drawn", "Off": "offsides"},
    "keeper": {"Saves": "saves"},
}

# Top-level groups that hold season totals (never per-90 rates). Used to prefer
# a totals group when a leaf is ambiguous; the hard rule is excluding per-90.
_TOTAL_GROUPS = (
    "Performance", "Standard", "Playing Time", "Expected",
    "Tackles", "Pass Types",
)
_PER90_GROUP = "Per 90 Minutes"


def _to_num(v):
    try:
        return float(v) if v not in (None, "") else 0.0
    except (TypeError, ValueError):
        return 0.0


def _to_int(v):
    try:
        return int(str(v).split("-")[0])  # FBref age like "25-031"
    except (TypeError, ValueError):
        return None


def map_fbref_row(row, league, season):
    """Map one flat FBref record to our flat player+stats dict.

    Pure function over a plain dict with simple string keys (FBref leaf names).
    Returns a single flat dict containing both player metadata and every
    canonical stat (missing stats default to 0).
    """
    out = {
        "player_id": f"{league}:{row.get('player')}",
        "name": row.get("player"),
        "position": row.get("pos"),
        "club": row.get("team"),
        "league": league,
        "age": _to_int(row.get("age")),
        "season": season,
    }
    for canonical, fbref_col in FBREF_MAP.items():
        out[canonical] = _to_num(row.get(fbref_col, 0))
    return out


def _leaf(col):
    return col[-1] if isinstance(col, tuple) else col


def _group(col):
    return col[0] if isinstance(col, tuple) else None


def _pick_total_column(df, leaf):
    """Return the column for ``leaf`` that is a season total, not a per-90 rate."""
    cands = [c for c in df.columns if _leaf(c) == leaf]
    cands = [c for c in cands if _group(c) != _PER90_GROUP]
    if not cands:
        return None
    for c in cands:
        if _group(c) in _TOTAL_GROUPS:
            return c
    return cands[0]


def _extract(df, leaf_map):
    """Project ``df`` down to one column per canonical stat, indexed by player."""
    out = pd.DataFrame(index=df.index)
    for leaf, canonical in leaf_map.items():
        col = _pick_total_column(df, leaf)
        out[canonical] = df[col] if col is not None else 0
    return out


def scrape_league(conn, league, season):
    """Scrape one league-season and write players + stats. Returns row count.

    Reads each FBref stat table, extracts season totals, merges on the player
    row-index, and aggregates multi-stint (transferred) players by summing
    totals. Live network call; soccerdata caches responses on disk.
    """
    import soccerdata as sd

    fb = sd.FBref(leagues=league, seasons=season)
    standard = fb.read_player_season_stats(stat_type="standard")

    merged = None
    for stat_type, leaf_map in STAT_TABLES.items():
        if stat_type == "standard":
            df = standard
        else:
            try:
                df = fb.read_player_season_stats(stat_type=stat_type)
            except Exception:
                # Some tables (e.g. keeper) may be absent for a league/season.
                continue
        part = _extract(df, leaf_map)
        merged = part if merged is None else merged.join(part, how="outer")

    if merged is None:
        return 0

    for col in STAT_COLUMNS:
        if col not in merged.columns:
            merged[col] = 0
    merged[STAT_COLUMNS] = merged[STAT_COLUMNS].apply(pd.to_numeric, errors="coerce").fillna(0)

    # Recover position / age from the standard table.
    pos_col = _pick_total_column(standard, "pos")
    age_col = _pick_total_column(standard, "age")
    meta = pd.DataFrame(index=standard.index)
    meta["position"] = standard[pos_col] if pos_col is not None else None
    meta["age"] = standard[age_col] if age_col is not None else None
    merged = merged.join(meta, how="left")

    # Flatten the index into columns so we can aggregate per player.
    flat = merged.reset_index()
    minute_col = "minutes"

    written = set()
    # Group by player name within this league-season; sum totals across stints,
    # take metadata from the highest-minutes stint.
    for name, grp in flat.groupby("player"):
        if name is None or (isinstance(name, float) and pd.isna(name)) or str(name).strip() == "":
            continue
        player_id = f"{league}:{name}"
        top = grp.sort_values(minute_col, ascending=False).iloc[0]
        age = top.get("age")
        pos = top.get("position")
        player = {
            "player_id": player_id,
            "name": name,
            "position": None if pd.isna(pos) else str(pos),
            "club": top.get("team") if "team" in grp.columns else None,
            "league": league,
            "age": _to_int(age) if not pd.isna(age) else None,
        }
        stats = {"player_id": player_id, "season": season}
        for col in STAT_COLUMNS:
            stats[col] = float(grp[col].sum())

        repo.upsert_player(conn, player)
        repo.upsert_player_stats(conn, stats)
        written.add(player_id)

    return len(written)


def scrape_all(conn):
    """Scrape all configured leagues for the configured season."""
    total = 0
    for lg in LEAGUES:
        total += scrape_league(conn, lg, SEASON)
    return total
