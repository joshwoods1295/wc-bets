"""Import WC 2026 squads into the database using player name matching.

Run AFTER scrape_data.py (player records must exist first).

Usage:
    ~/.venvs/wcbets/bin/python import_squads.py

Reads data/squads/squads.csv (name,country) and matches each player
to their record in the database by normalised name (accent-stripped,
case-insensitive). Prints a summary of what matched and what didn't.
"""
import sys
import unicodedata
from pathlib import Path

SQUADS_CSV = Path(__file__).resolve().parent / "data" / "squads" / "squads.csv"


def normalise(name):
    nfkd = unicodedata.normalize("NFKD", name or "")
    no_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    # also strip punctuation that differs between sources (apostrophes, hyphens)
    cleaned = no_accents.casefold().strip()
    return cleaned


try:
    import soccerdata  # noqa: F401  (just to verify venv)
except ImportError:
    print("ERROR: Wrong Python / venv.")
    print("Run with: ~/.venvs/wcbets/bin/python import_squads.py")
    sys.exit(1)

from wcbets.config import DB_PATH
from wcbets.db import repository as repo

conn = repo.connect(DB_PATH)
repo.init_db(conn)

# Check players exist
n_players = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
if n_players == 0:
    print("No players in database yet.")
    print("Run scrape_data.py first, then re-run this script.")
    sys.exit(1)

print(f"Database has {n_players} players. Building name index...")

# Build normalised-name → list of player_ids
name_index = {}
for pid, name in conn.execute("SELECT player_id, name FROM players"):
    key = normalise(name)
    name_index.setdefault(key, []).append(pid)

print(f"Name index built ({len(name_index)} unique names).")
print()

# Read squads CSV
import csv
rows = []
with open(SQUADS_CSV, newline="") as f:
    for r in csv.DictReader(f):
        rows.append((r["name"].strip(), r["country"].strip()))

matched = 0
unmatched = []
ambiguous = []
already_linked = 0

for name, country in rows:
    key = normalise(name)
    hits = name_index.get(key, [])

    if len(hits) == 1:
        try:
            repo.upsert_squad_member(conn, hits[0], country)
            matched += 1
        except Exception:
            already_linked += 1
    elif len(hits) == 0:
        unmatched.append((name, country))
    else:
        # Multiple players share this normalised name (e.g. two "David Silva"s)
        ambiguous.append((name, country, hits))

print(f"Results for {len(rows)} squad entries:")
print(f"  ✅  Matched and imported : {matched}")
if already_linked:
    print(f"  ℹ️   Already in database  : {already_linked}")
if ambiguous:
    print(f"  ⚠️   Ambiguous (skipped)  : {len(ambiguous)}")
    for name, country, hits in ambiguous:
        print(f"       '{name}' ({country}) matched {len(hits)} players:")
        for pid in hits:
            print(f"         {pid}")
if unmatched:
    print(f"  ❌  Not found in DB     : {len(unmatched)}")
    print()
    print("  The following players weren't matched. This usually means:")
    print("  their league wasn't scraped, FBref uses a different spelling,")
    print("  or the player_id format is slightly off.")
    print()
    for name, country in unmatched:
        print(f"    {country}: {name}")

print()
countries = conn.execute(
    "SELECT country, COUNT(*) FROM national_squads GROUP BY country ORDER BY country"
).fetchall()
if countries:
    print("Squads now in database:")
    for country, count in countries:
        print(f"  {country}: {count} players")
else:
    print("No squads in database yet.")
