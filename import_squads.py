"""Import all WC 2026 squads from Wikipedia (all 48 nations).

Run AFTER scrape_data.py (player records must exist first).

Usage:
    ~/.venvs/wcbets/bin/python import_squads.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import soccerdata  # noqa: F401
except ImportError:
    print("ERROR: Wrong Python / venv.")
    print("Run with: ~/.venvs/wcbets/bin/python import_squads.py")
    sys.exit(1)

from wcbets.config import DB_PATH
from wcbets.db import repository as repo
from wcbets.scrape.wiki_squads import import_squads

conn = repo.connect(DB_PATH)
repo.init_db(conn)

n = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
if n == 0:
    print("No players in database yet. Run scrape_data.py first.")
    sys.exit(1)

print(f"Database has {n} players.\n")
import_squads(conn)
