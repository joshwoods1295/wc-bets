import json
from pathlib import Path
from wcbets.scrape.league_scraper import map_fbref_row

SAMPLE = json.loads((Path(__file__).parent / "fixtures" / "fbref_sample.json").read_text())

def test_map_fbref_row_to_canonical():
    out = map_fbref_row(SAMPLE[0], league="ENG-Premier League", season="2024")
    assert out["name"] == "A Back"
    assert out["minutes"] == 1800
    assert out["fouls"] == 40
    assert out["fouls_drawn"] == 12
    assert out["tackles"] == 55
    assert out["yellows"] == 8
    assert out["league"] == "ENG-Premier League"
    assert out["season"] == "2024"

def test_map_fbref_row_handles_missing_columns():
    minimal = {"player": "C Sub", "Min": 90}
    out = map_fbref_row(minimal, league="ENG-Premier League", season="2024")
    assert out["minutes"] == 90
    assert out["goals"] == 0  # missing -> default 0
