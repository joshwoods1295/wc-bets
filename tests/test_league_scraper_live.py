import socket

import pytest

from wcbets.db import repository as repo
from wcbets.scrape import league_scraper


def _online():
    try:
        socket.create_connection(("fbref.com", 443), timeout=5).close()
        return True
    except OSError:
        return False


@pytest.mark.skipif(not _online(), reason="needs network/FBref")
def test_scrape_league_populates_fouls(tmp_path):
    conn = repo.connect(tmp_path / "live.db")
    repo.init_db(conn)
    n = league_scraper.scrape_league(conn, "ENG-Premier League", "2024")
    assert n > 100  # a full league season of players
    total_fouls = conn.execute("SELECT SUM(fouls) FROM player_stats").fetchone()[0]
    assert total_fouls and total_fouls > 0
    total_tkl = conn.execute("SELECT SUM(tackles) FROM player_stats").fetchone()[0]
    assert total_tkl and total_tkl > 0
    # at least one player with many fouls (sanity that totals, not per90, stored)
    mx = conn.execute("SELECT MAX(fouls) FROM player_stats").fetchone()[0]
    assert mx > 20
