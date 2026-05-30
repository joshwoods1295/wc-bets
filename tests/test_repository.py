from wcbets.db import repository as repo

def test_init_db_creates_tables(tmp_path):
    db = tmp_path / "t.db"
    conn = repo.connect(db)
    repo.init_db(conn)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"players", "player_stats", "national_squads",
            "fixtures", "backlog"} <= tables

def test_upsert_player_is_idempotent(tmp_path):
    conn = repo.connect(tmp_path / "t.db")
    repo.init_db(conn)
    row = {"player_id": "p1", "name": "A Back", "position": "LB",
           "club": "X", "league": "ENG-Premier League", "age": 25}
    repo.upsert_player(conn, row)
    repo.upsert_player(conn, {**row, "club": "Y"})  # second time updates
    out = conn.execute("SELECT name, club FROM players WHERE player_id='p1'").fetchone()
    assert out == ("A Back", "Y")
    assert conn.execute("SELECT COUNT(*) FROM players").fetchone()[0] == 1
