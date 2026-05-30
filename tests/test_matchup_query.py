from wcbets.db import repository as repo
from wcbets.analysis.matchup_query import players_by_country, peer_distribution

def _seed(conn):
    repo.init_db(conn)
    for pid, name, pos, fouls, fld, mins, country in [
        ("p1", "LB One", "DF", 40, 5, 1800, "England"),
        ("p2", "RW Two", "FW", 8, 50, 1710, "France"),
        ("p3", "DF Three", "DF", 10, 4, 1800, "Spain"),
    ]:
        repo.upsert_player(conn, {"player_id": pid, "name": name, "position": pos,
                                  "club": "X", "league": "L", "age": 25})
        repo.upsert_player_stats(conn, {"player_id": pid, "season": "2024",
            "minutes": mins, "shots": 0, "shots_on_target": 0, "goals": 0,
            "assists": 0, "fouls": fouls, "fouls_drawn": fld, "yellows": 0,
            "reds": 0, "offsides": 0, "tackles": 0, "corners_taken": 0, "saves": 0})
        repo.upsert_squad_member(conn, pid, country)

def test_players_by_country(tmp_path):
    conn = repo.connect(tmp_path / "t.db"); _seed(conn)
    eng = players_by_country(conn, "England")
    assert len(eng) == 1 and eng[0]["name"] == "LB One"
    assert eng[0]["fouls_p90"] > 0

def test_peer_distribution_for_position(tmp_path):
    conn = repo.connect(tmp_path / "t.db"); _seed(conn)
    dist = peer_distribution(conn, "DF", "fouls_p90")
    assert len(dist) == 2  # p1 and p3 are DF
