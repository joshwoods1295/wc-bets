"""Best-effort live integration test for the FBref scraper.

Skips when offline or when FBref is unparseable (outside our control).
When it runs, verifies fouls and shots are populated as season totals.
Note: tackles and corners_taken are 0 (soccerdata 1.9 dropped those tables).
"""
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

    try:
        n = league_scraper.scrape_league(conn, "ENG-Premier League", "2024")
    except Exception as exc:
        pytest.skip(f"FBref scrape unavailable at test time: {exc!r}")

    if n == 0:
        pytest.skip("FBref returned no players (rate-limited or empty page)")

    assert n > 100
    assert conn.execute("SELECT SUM(fouls) FROM player_stats").fetchone()[0] > 0
    assert conn.execute("SELECT SUM(shots) FROM player_stats").fetchone()[0] > 0
    # Verify season totals, not per-90 (a high-foul player should have >20)
    assert conn.execute("SELECT MAX(fouls) FROM player_stats").fetchone()[0] > 20
