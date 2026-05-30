"""Import WC 2026 squads into the database using player name matching.

Run AFTER scrape_data.py (player records must exist first).

Usage:
    ~/.venvs/wcbets/bin/python import_squads.py

Reads data/squads/squads.csv (name,country), matches each player to their
DB record by normalised name, and writes to national_squads. Resolves
ambiguous (same name across leagues) by picking the player with the most
minutes. Re-running is safe (clears squads and reimports cleanly).
"""
import csv
import sys
import unicodedata
from pathlib import Path

SQUADS_CSV = Path(__file__).resolve().parent / "data" / "squads" / "squads.csv"


def normalise(name):
    nfkd = unicodedata.normalize("NFKD", name or "")
    no_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    return no_accents.casefold().strip()


def prefix_match(query_tokens, candidate_tokens):
    """True if every token in query appears (in order) at the start of candidate."""
    if len(query_tokens) > len(candidate_tokens):
        return False
    return all(q == c for q, c in zip(query_tokens, candidate_tokens))


try:
    import soccerdata  # noqa: F401
except ImportError:
    print("ERROR: Wrong Python / venv.")
    print("Run with: ~/.venvs/wcbets/bin/python import_squads.py")
    sys.exit(1)

from wcbets.config import DB_PATH
from wcbets.db import repository as repo

conn = repo.connect(DB_PATH)
repo.init_db(conn)

n_players = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
if n_players == 0:
    print("No players in database yet. Run scrape_data.py first.")
    sys.exit(1)

print(f"Database has {n_players} players. Building name index...")

# normalised name -> list of (player_id, minutes)
name_index = {}
for pid, name in conn.execute("SELECT player_id, name FROM players"):
    key = normalise(name)
    mins = conn.execute(
        "SELECT COALESCE(minutes,0) FROM player_stats WHERE player_id=?", (pid,)
    ).fetchone()
    name_index.setdefault(key, []).append((pid, mins[0] if mins else 0))

print(f"Name index built ({len(name_index)} unique names).")
print()

# Clear existing squad data so re-runs are idempotent
conn.execute("DELETE FROM national_squads")
conn.commit()

rows = []
with open(SQUADS_CSV, newline="") as f:
    for r in csv.DictReader(f):
        rows.append((r["name"].strip(), r["country"].strip()))

matched = 0
resolved_ambiguous = 0
unmatched = []

for name, country in rows:
    key = normalise(name)
    hits = name_index.get(key, [])

    # Fallback: prefix-token match (handles "Fabian Ruiz" -> "Fabian Ruiz Peña")
    if not hits:
        q_tokens = key.split()
        hits = []
        for db_key, entries in name_index.items():
            c_tokens = db_key.split()
            if len(q_tokens) >= 2 and prefix_match(q_tokens, c_tokens):
                hits.extend(entries)

    if not hits:
        unmatched.append((name, country))
        continue

    if len(hits) == 1:
        repo.upsert_squad_member(conn, hits[0][0], country)
        matched += 1
    else:
        # Ambiguous: pick the player_id with the most minutes
        best = max(hits, key=lambda x: x[1])
        repo.upsert_squad_member(conn, best[0], country)
        resolved_ambiguous += 1

print(f"Results for {len(rows)} squad entries:")
print(f"  ✅  Matched             : {matched}")
if resolved_ambiguous:
    print(f"  ✅  Resolved (max mins) : {resolved_ambiguous}")
if unmatched:
    print(f"  ⚠️   Not in DB          : {len(unmatched)}")
    print()
    print("  These players have no Big-5 stats (non-European league,")
    print("  goalkeeper with 0 appearances, or unknown FBref spelling).")
    print("  They won't appear in matchup flags but that's expected —")
    print("  we have no stats to base a flag on.")
    print()
    for name, country in unmatched:
        print(f"    {country}: {name}")

print()
countries = conn.execute(
    "SELECT country, COUNT(*) FROM national_squads GROUP BY country ORDER BY country"
).fetchall()
print("Squads now in database:")
for country, count in countries:
    print(f"  {country}: {count} players")
