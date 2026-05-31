"""Scrape per-player season stats from Sofascore.

Replaces the soccerdata/FBref pipeline. Uses Sofascore's unofficial API
which responds to plain requests (no auth required). Data is cached on
disk so re-runs are fast.

Coverage: all Big 5 leagues, full stat set including tackles and fouls.
Not available: corners_taken (Sofascore doesn't expose this per-player).
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import requests

from wcbets.config import STAT_COLUMNS
from wcbets.db import repository as repo

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE = "https://api.sofascore.com/api/v1"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://www.sofascore.com/",
}
REQUEST_DELAY = 0.25   # seconds between API calls
CACHE_DIR = Path.home() / ".cache" / "sofascore"

# League name -> (tournament_id, season_id)
LEAGUES: dict[str, tuple[int, int]] = {
    # Big 5 (already scraped)
    "ENG-Premier League": (17,  61627),
    "ESP-La Liga":        (8,   61643),
    "ITA-Serie A":        (23,  63515),
    "GER-Bundesliga":     (35,  63516),
    "FRA-Ligue 1":        (34,  61736),
    # Extended coverage — covers most WC squad players outside Big 5
    "POR-Primeira Liga":  (238, 63670),   # Cancelo, Otamendi, Diogo Costa...
    "NED-Eredivisie":     (37,  61666),   # Dest, Pepi, van Dijk backup clubs...
    "TUR-Super Lig":      (52,  63814),   # Kante (Fenerbahce), Osimhen (Galatasaray)...
    "SCO-Premiership":    (36,  62408),   # Trusty (Celtic/USA), Maeda (Celtic/Japan)...
    "ENG-Championship":   (18,  61961),   # Aaronson (Leeds), Wright (Coventry)...
    "KSA-Pro League":     (955, 63998),   # Fabinho, Neymar-era Saudi players...
    "USA-MLS":            (242, 70158),   # Turner, Ream, Robinson, many USA players...
    "BRA-Serie A":        (325, 72034),   # Flamengo (Alex Sandro, Danilo, Leo Pereira)...
    "ARG-Primera":        (155, 87913),   # Argentine domestic players...
    "AUT-Bundesliga":     (45,  62629),   # Salzburg pipeline, Austrian WC players...
}

# Sofascore field -> our canonical stat column
STAT_MAP = {
    "minutesPlayed": "minutes",
    "totalShots":    "shots",
    "shotsOnTarget": "shots_on_target",
    "goals":         "goals",
    "assists":       "assists",
    "fouls":         "fouls",
    "wasFouled":     "fouls_drawn",
    "yellowCards":   "yellows",
    "redCards":      "reds",
    "offsides":      "offsides",
    "tackles":       "tackles",
    "saves":         "saves",
    # corners_taken: not available per-player on Sofascore
}

_POS = {"G": "GK", "D": "DF", "M": "MF", "F": "FW"}


# ---------------------------------------------------------------------------
# HTTP + cache helpers
# ---------------------------------------------------------------------------

def _cache_path(key: str) -> Path:
    return CACHE_DIR / (key.replace("/", "_").replace("?", "_") + ".json")


def _get(url: str, cache_key: str | None = None, retries: int = 2) -> dict:
    """GET url, using disk cache when cache_key is given."""
    if cache_key:
        p = _cache_path(cache_key)
        if p.exists():
            return json.loads(p.read_text())

    for attempt in range(retries + 1):
        try:
            time.sleep(REQUEST_DELAY)
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                data = r.json()
                if cache_key:
                    CACHE_DIR.mkdir(parents=True, exist_ok=True)
                    _cache_path(cache_key).write_text(json.dumps(data))
                return data
            if r.status_code == 404:
                return {}
        except Exception:
            if attempt == retries:
                return {}
        time.sleep(1)
    return {}


# ---------------------------------------------------------------------------
# API accessors
# ---------------------------------------------------------------------------

def get_teams(tournament_id: int, season_id: int) -> list[dict]:
    """Return list of {id, name} for all teams in a league-season."""
    data = _get(
        f"{BASE}/unique-tournament/{tournament_id}/season/{season_id}/standings/total",
        cache_key=f"standings_{tournament_id}_{season_id}",
    )
    rows = []
    for group in data.get("standings", []):
        for row in group.get("rows", []):
            t = row.get("team", {})
            rows.append({"id": t["id"], "name": t["name"]})
    # Deduplicate
    seen = set()
    return [t for t in rows if not (t["id"] in seen or seen.add(t["id"]))]


def get_squad(team_id: int) -> list[dict]:
    """Return list of {id, name, position} for a team's current squad."""
    data = _get(
        f"{BASE}/team/{team_id}/players",
        cache_key=f"squad_{team_id}",
    )
    players = []
    for entry in data.get("players", []):
        p = entry.get("player", entry)
        players.append({
            "id": p.get("id"),
            "name": p.get("name", ""),
            "position": _POS.get(p.get("position", ""), None),
        })
    return [p for p in players if p["id"] and p["name"]]


def get_player_stats(player_id: int, tournament_id: int, season_id: int) -> dict:
    """Return raw Sofascore statistics dict for one player in one season."""
    data = _get(
        f"{BASE}/player/{player_id}/unique-tournament/{tournament_id}"
        f"/season/{season_id}/statistics/overall",
        cache_key=f"stats_{player_id}_{tournament_id}_{season_id}",
    )
    return data.get("statistics", {})


def _parse_age(player_dict: dict) -> int | None:
    dob = player_dict.get("dateOfBirthTimestamp")
    if dob:
        from datetime import datetime
        return datetime.now().year - datetime.fromtimestamp(dob).year
    return None


# ---------------------------------------------------------------------------
# League scraper
# ---------------------------------------------------------------------------

def scrape_league(conn, league: str, season: str = "2024") -> int:
    """Scrape one league-season from Sofascore and write to DB.

    Returns the number of players written.
    """
    tournament_id, season_id = LEAGUES[league]

    teams = get_teams(tournament_id, season_id)
    if not teams:
        print(f"    No teams found for {league} — skipping.")
        return 0

    # Collect all players across all teams (dedup by Sofascore player id)
    all_players: dict[int, dict] = {}
    for team in teams:
        squad = get_squad(team["id"])
        for p in squad:
            if p["id"] not in all_players:
                all_players[p["id"]] = {**p, "team": team["name"]}

    # Fetch stats for each player; aggregate for those with multiple stints
    # (Sofascore's /statistics/overall already aggregates across teams in the
    # same tournament, so we just fetch once per player per season.)
    written = 0
    for sofascore_id, pinfo in all_players.items():
        stats = get_player_stats(sofascore_id, tournament_id, season_id)
        if not stats:
            continue

        player_id = f"{league}:{pinfo['name']}"

        db_player = {
            "player_id": player_id,
            "name": pinfo["name"],
            "position": pinfo.get("position"),
            "club": pinfo["team"],
            "league": league,
            "age": None,
        }

        db_stats: dict = {"player_id": player_id, "season": season}
        for ss_key, canonical in STAT_MAP.items():
            db_stats[canonical] = float(stats.get(ss_key) or 0)
        # Fill any STAT_COLUMNS not covered by STAT_MAP with 0
        for col in STAT_COLUMNS:
            if col not in db_stats:
                db_stats[col] = 0.0

        repo.upsert_player(conn, db_player)
        repo.upsert_player_stats(conn, db_stats)
        written += 1

    return written


def scrape_all(conn) -> int:
    total = 0
    for league in LEAGUES:
        total += scrape_league(conn, league)
    return total
