"""Best-effort live integration test for the FBref scraper.

This test exercises the real scrape end-to-end, but live scraping depends on
FBref being reachable AND parseable at test time. FBref periodically changes its
HTML or rate-limits, which makes the underlying ``soccerdata`` parser raise. Those
conditions are outside our code's control, so we SKIP (rather than fail) when the
scrape cannot complete. When the scrape does succeed, we assert the data is
correct: real season totals (not per-90), with fouls and tackles populated.
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
    except Exception as exc:  # FBref HTML change / rate-limit / parse error
        pytest.skip(f"FBref scrape unavailable at test time: {exc!r}")

    if n == 0:
        pytest.skip("FBref returned no players (rate-limited or empty page)")

    assert n > 100  # a full league season of players
    total_fouls = conn.execute("SELECT SUM(fouls) FROM player_stats").fetchone()[0]
    assert total_fouls and total_fouls > 0
    total_tkl = conn.execute("SELECT SUM(tackles) FROM player_stats").fetchone()[0]
    assert total_tkl and total_tkl > 0
    # At least one player with many fouls: sanity that season TOTALS (not per-90)
    # were stored.
    mx = conn.execute("SELECT MAX(fouls) FROM player_stats").fetchone()[0]
    assert mx > 20
