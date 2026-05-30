import pytest

from wcbets.scrape.wc_scraper import (
    normalise_name, match_player, scrape_fixtures, scrape_squads,
)


def test_normalise_name_strips_accents_and_case():
    assert normalise_name("Kylian Mbappé") == "kylian mbappe"


def test_match_player_by_normalised_name():
    players = [{"player_id": "p1", "name": "Kylian Mbappé"},
               {"player_id": "p2", "name": "Harry Kane"}]
    assert match_player("kylian mbappe", players) == "p1"
    assert match_player("unknown guy", players) is None


def test_scrape_fixtures_raises_with_guidance():
    with pytest.raises(NotImplementedError) as e:
        scrape_fixtures(None)
    assert "manual" in str(e.value).lower()


def test_scrape_squads_raises_with_guidance():
    with pytest.raises(NotImplementedError):
        scrape_squads(None, "England", None)
