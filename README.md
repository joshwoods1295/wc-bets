# WC Bets

Scrapes bettable per-player football stats into SQLite, maps players to World Cup
2026 squads, and flags notable positional matchups (e.g. a high-fouling left-back
against a winger who draws lots of fouls).

## Setup

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

> **macOS / iCloud note:** if this project lives under an iCloud-synced
> `~/Documents`, iCloud can corrupt the virtualenv while it is being created
> (pip ends up half-written). Create the venv *outside* iCloud, e.g.
> `python3.12 -m venv ~/.venvs/wcbets`, and use `~/.venvs/wcbets/bin/...`.

## Collect data

```python
from wcbets.db import repository as repo
from wcbets.scrape import league_scraper
from wcbets.config import DB_PATH

conn = repo.connect(DB_PATH)
repo.init_db(conn)
league_scraper.scrape_all(conn)   # league player stats (slow; cached by soccerdata)
```

Stats are stored as season totals plus per-90 values. Bettable markets covered:
shots, shots on target, goals, assists, fouls, fouls drawn, yellow/red cards,
offsides, tackles, corners taken, saves, minutes.

> **Scraping is best-effort.** Data comes from FBref via `soccerdata`. FBref
> periodically changes its HTML or rate-limits requests, which can make a scrape
> fail transiently — re-run later, or use the manual CSV path below. The library
> is pinned to `soccerdata>=1.8,<1.9`: version 1.9 dropped the `defense` (tackles)
> and `passing_types` (corners) player tables we rely on.

## World Cup squads & fixtures (manual import)

Automated WC squad/fixture scraping is **not** available: `soccerdata`'s FBref
backend does not expose international tournaments, and final squads are published
only just before the tournament. Use the CSV import with the templates in
`data/templates/`:

```python
from wcbets.scrape import manual_import

manual_import.import_squads(conn, "data/templates/squads_template.csv")
# cols: player_id,country
manual_import.import_fixtures(conn, "data/templates/fixtures_template.csv")
# cols: match_id,date,home_country,away_country,stage
```

`player_id` is `"<league>:<player name>"`, e.g. `ENG-Premier League:Harry Kane`.

## Run the dashboard

```bash
streamlit run wcbets/app/dashboard.py
```

Pick two countries to see flagged positional matchups, plus a backlog tab for
future-work ideas.

## Test

```bash
pytest -q
```

22 unit/logic tests plus one live FBref integration test. The live test **skips**
(rather than fails) when FBref is offline or unparseable, since that is outside
this project's control.
