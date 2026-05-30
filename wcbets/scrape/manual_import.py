"""CSV import fallback for squads and fixtures."""
import csv as csvmod
from wcbets.db import repository as repo


def import_squads(conn, csv_path):
    count = 0
    with open(csv_path, newline="") as f:
        for r in csvmod.DictReader(f):
            repo.upsert_squad_member(conn, r["player_id"], r["country"])
            count += 1
    return count


def import_fixtures(conn, csv_path):
    count = 0
    with open(csv_path, newline="") as f:
        for r in csvmod.DictReader(f):
            repo.upsert_fixture(conn, {
                "match_id": r["match_id"],
                "date": r.get("date"),
                "home_country": r["home_country"],
                "away_country": r["away_country"],
                "stage": r.get("stage"),
            })
            count += 1
    return count
