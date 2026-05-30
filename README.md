# WC Bets

Scrapes bettable per-player football stats into SQLite, maps players to World Cup
2026 squads, and flags notable positional matchups (e.g. a high-fouling left-back
against a winger who draws lots of fouls).

## Setup
```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Collect data
```python
from wcbets.db import repository as repo
from wcbets.scrape import league_scraper
from wcbets.config import DB_PATH
conn = repo.connect(DB_PATH); repo.init_db(conn)
league_scraper.scrape_all(conn)        # league player stats (slow; cached by soccerdata)
```

### World Cup squads & fixtures (manual import)
Automated WC squad/fixture scraping is not available (soccerdata's FBref backend
does not expose international tournaments, and squads are published only just before
the tournament). Use the CSV import with the templates in `data/templates/`:
```python
from wcbets.scrape import manual_import
manual_import.import_squads(conn, "data/templates/squads_template.csv")     # cols: player_id,country
manual_import.import_fixtures(conn, "data/templates/fixtures_template.csv") # cols: match_id,date,home_country,away_country,stage
```
`player_id` is `"<league>:<player name>"`, e.g. `ENG-Premier League:Harry Kane`.

## Run the dashboard
```bash
streamlit run wcbets/app/dashboard.py
```

## Test
```bash
pytest -q          # unit tests; one live FBref integration test runs only with network
```
