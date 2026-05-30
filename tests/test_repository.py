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


def test_backlog_add_list_complete(tmp_path):
    conn = repo.connect(tmp_path / "t.db")
    repo.init_db(conn)
    bid = repo.add_backlog_item(conn, "ML projections", "v2 idea", now="2026-05-30")
    items = repo.list_backlog(conn)
    assert len(items) == 1 and items[0]["status"] == "open"
    repo.complete_backlog_item(conn, bid)
    assert repo.list_backlog(conn)[0]["status"] == "done"

def test_seed_backlog_is_idempotent(tmp_path):
    conn = repo.connect(tmp_path / "t.db")
    repo.init_db(conn)
    repo.seed_backlog(conn, now="2026-05-30")
    repo.seed_backlog(conn, now="2026-05-30")  # second call adds nothing
    titles = [i["title"] for i in repo.list_backlog(conn)]
    assert "ML projections of player stats" in titles
    assert len(titles) == 4
