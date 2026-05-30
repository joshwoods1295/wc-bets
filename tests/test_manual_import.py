from wcbets.db import repository as repo
from wcbets.scrape import manual_import


def test_import_squads_csv(tmp_path):
    conn = repo.connect(tmp_path / "t.db")
    repo.init_db(conn)
    # player must exist for FK; insert minimally
    repo.upsert_player(conn, {"player_id": "p1", "name": "A", "position": "LB",
                              "club": "X", "league": "ENG-Premier League", "age": 25})
    csv = tmp_path / "squad.csv"
    csv.write_text("player_id,country\np1,England\n")
    n = manual_import.import_squads(conn, csv)
    assert n == 1
    row = conn.execute("SELECT country FROM national_squads WHERE player_id='p1'").fetchone()
    assert row == ("England",)


def test_import_fixtures_csv(tmp_path):
    conn = repo.connect(tmp_path / "t.db")
    repo.init_db(conn)
    csv = tmp_path / "fix.csv"
    csv.write_text("match_id,date,home_country,away_country,stage\n"
                   "m1,2026-06-11,England,France,Group A\n")
    n = manual_import.import_fixtures(conn, csv)
    assert n == 1
    row = conn.execute("SELECT home_country, away_country FROM fixtures WHERE match_id='m1'").fetchone()
    assert row == ("England", "France")
