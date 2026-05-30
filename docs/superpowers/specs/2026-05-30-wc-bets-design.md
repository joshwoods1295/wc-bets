# WC Bets — Design Spec

**Date:** 2026-05-30
**Status:** Approved (design)

## Goal

Scrape granular per-player football league statistics, store them in a queryable
database, map players to their World Cup 2026 national squads, and surface notable
positional matchups for a given fixture to support betting decisions.

Example target insight: *a left-back who fouls a lot lined up against a right-winger
who draws a lot of fouls.*

The system outputs **positional matchup flags** — transparent, explainable signals.
The betting judgement stays with the user. No ML model and no bookmaker-odds
comparison in this version.

## Decisions (from brainstorming)

| Question | Decision |
|----------|----------|
| Data source | Scrape FBref via the `soccerdata` library (richest free per-player data; rate-limited + cached) |
| League scope | Big-5 European leagues + extras: Eredivisie, Primeira Liga, MLS, Saudi Pro League |
| Interface | Simple web dashboard (Streamlit) |
| Output | Positional matchup flags |
| WC mapping | Auto-scrape national squads + fixtures, **with a manual-override import fallback** |
| Stack | Python end-to-end (soccerdata / pandas / SQLite / Streamlit) |

## Architecture

Four components with clean boundaries:

### 1. Scraper (`scraper/`)
- `league_scraper`: uses `soccerdata` (FBref backend) to pull per-player season stats
  for the in-scope leagues. Stat groups:
  - **defense**: tackles, tackles won
  - **misc**: fouls committed, fouls drawn, yellow cards, red cards, aerial duels won,
    ball recoveries
  - **passing / pass-types**: corners taken
  - **playing time**: minutes played (required for per-90 normalisation)
- `wc_scraper`: pulls WC 2026 national squads and the fixture list
  (FBref national-team pages, with Wikipedia as a fallback source).
- `manual_import`: CSV/paste import for squads and fixtures, used when the auto-scrape
  is late, incomplete, or unavailable. Squads are not reliably published until just
  before the tournament, so this fallback is a first-class path, not an afterthought.
- Writes rows to the database. Respectful scraping: throttled requests with local
  caching so re-runs are cheap and we do not hammer the source.

### 2. Database (`db/` — SQLite)
Core tables:
- `players` — id, name, primary position, club, league, age
- `player_stats` — player_id, season, minutes, fouls, fouls_drawn, tackles,
  tackles_won, yellows, reds, aerials_won, recoveries, corners_taken; stored as
  season totals plus computed per-90 values
- `national_squads` — player_id, country (links league players to their WC team)
- `fixtures` — match_id, date, home_country, away_country, stage/group

### 3. Matchup engine (`analysis/`)
- Pure-Python, no network, independently unit-testable.
- Normalises stats to per-90 minutes.
- Ranks each player against positional peers via percentiles.
- Emits a **flag** when a notable mismatch exists, e.g. attacking-side fouls-drawn rate
  ≥ configurable percentile AND opposing defender foul rate ≥ configurable percentile.
- Thresholds are configurable. Output is explainable: every flag carries the underlying
  per-90 numbers and percentiles that triggered it.

### 4. Dashboard (`app/` — Streamlit)
- Select a WC fixture (or pick any two teams / players manually).
- View each side's squad, positional matchups, and highlighted flags with the
  supporting per-90 figures and percentile ranks.

## Data flow

```
soccerdata (FBref)  ->  SQLite (raw totals + per-90)  ->  matchup engine (percentiles + flags)  ->  Streamlit dashboard
manual_import (CSV) --^ (squads / fixtures fallback)
```

## Testing

- **Matchup engine + per-90 / percentile logic**: unit tests, deterministic, no network.
- **Scrapers**: thin tests against saved sample HTML / fixtures so CI never hits FBref.
- **Manual import**: tests for CSV parsing and DB upsert.

## Out of scope (this version)

- Machine-learning projections of player stats.
- Bookmaker-odds ingestion and +EV value detection.
- Real-time / in-play data.

These are natural follow-ups once the stats DB and matchup flags are proven.

## Key risks

- **Squad availability**: final 26-man squads are announced just before the tournament
  and source pages lag. Mitigated by the manual-override import path.
- **Scrape fragility / rate limits**: FBref structure changes and throttling. Mitigated
  by using the maintained `soccerdata` wrapper, local caching, and respectful throttling.
- **Player name/identity matching** across league data and national squads. Will need a
  reconciliation step (FBref player IDs preferred over name matching).
