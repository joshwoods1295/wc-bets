"""Scrape player season stats from Sofascore into the database.

Usage:
    ~/.venvs/wcbets/bin/python scrape_data.py

Pulls per-player stats for all 5 major European leagues. First run
fetches from the Sofascore API (~15-20 min). Re-runs use the local
cache and complete in seconds.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from wcbets.scrape.sofascore_scraper import LEAGUES
except ImportError:
    print("ERROR: Wrong Python / venv.")
    print("Run with: ~/.venvs/wcbets/bin/python scrape_data.py")
    sys.exit(1)

from wcbets.config import DB_PATH
from wcbets.db import repository as repo
from wcbets.scrape import sofascore_scraper as ss

print("=" * 60)
print("WC Bets — Sofascore league data scraper")
print("=" * 60)
print()

conn = repo.connect(DB_PATH)
repo.init_db(conn)

print(f"Database : {DB_PATH}")
print(f"Leagues  : {len(LEAGUES)} (Big 5 + Primeira Liga, Eredivisie, Super Lig,")
print(f"           Scottish Prem, Championship, Saudi, MLS, Brazilian, Argentine, Austrian)")
print(f"Cache    : ~/.cache/sofascore/  (re-runs use cache, ~instant)")
print()

total = 0
for i, league in enumerate(LEAGUES, 1):
    print(f"[{i}/{len(LEAGUES)}] {league} ...", end=" ", flush=True)
    t0 = time.time()
    try:
        n = ss.scrape_league(conn, league)
        elapsed = time.time() - t0
        print(f"{n} players  ({elapsed:.0f}s)")
        total += n
    except Exception as e:
        print(f"FAILED — {e}")

print()
print(f"Done. {total} player-season rows written.")
print()
print("Next: run import_squads.py to import WC squads.")
