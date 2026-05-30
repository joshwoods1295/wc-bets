"""Run this once to pull all league player stats into the database.

Usage (from the project folder):
    ~/.venvs/wcbets/bin/python scrape_data.py

This takes 10-30 minutes. It's polite to FBref (pauses between requests)
and caches pages locally so re-runs are fast.
"""
import sys
import time
from pathlib import Path

print("=" * 60)
print("WC Bets — league data scraper")
print("=" * 60)
print()

# Check we're running from the right venv / have the right packages.
try:
    import soccerdata  # noqa: F401
except ImportError:
    print("ERROR: soccerdata not found.")
    print("Make sure you're running with the right Python, e.g.:")
    print("   ~/.venvs/wcbets/bin/python scrape_data.py")
    sys.exit(1)

import os, sys
os.chdir(Path(__file__).resolve().parent)  # always run from project root
sys.path.insert(0, str(Path(__file__).resolve().parent))

from wcbets.config import DB_PATH, LEAGUES, SEASON
from wcbets.db import repository as repo
from wcbets.scrape import league_scraper

print(f"Database: {DB_PATH}")
print(f"Season:   {SEASON}")
print(f"Leagues:  {len(LEAGUES)}")
print()

conn = repo.connect(DB_PATH)
repo.init_db(conn)

total = 0
for i, league in enumerate(LEAGUES, 1):
    print(f"[{i}/{len(LEAGUES)}] Scraping {league} ...", end=" ", flush=True)
    t0 = time.time()
    try:
        n = league_scraper.scrape_league(conn, league, SEASON)
        elapsed = time.time() - t0
        print(f"{n} players  ({elapsed:.0f}s)")
        total += n
    except Exception as e:
        print(f"SKIPPED — {e!r}")
        print("         FBref may be temporarily unavailable. Re-run later.")

print()
print(f"Done. {total} player-season rows written to database.")
print()
print("Next step: import WC squads.")
print("  Edit data/templates/squads_template.csv with real squads,")
print("  then run import_squads.py")
