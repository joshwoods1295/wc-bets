"""Central config: scope, paths, and flag thresholds."""
from pathlib import Path

# League names — keep in sync with LEAGUES dict in sofascore_scraper.py.
LEAGUES = [
    "ENG-Premier League", "ESP-La Liga", "ITA-Serie A",
    "GER-Bundesliga",     "FRA-Ligue 1",
    "POR-Primeira Liga",  "NED-Eredivisie",  "TUR-Super Lig",
    "SCO-Premiership",    "ENG-Championship","KSA-Pro League",
    "USA-MLS",            "BRA-Serie A",     "ARG-Primera",
    "AUT-Bundesliga",
]

SEASON = "2024"

# Stats we store (all bettable markets). Keys are canonical column names.
# tackles and fouls now populated via Sofascore.
# corners_taken: not available per-player from Sofascore; stays 0.
STAT_COLUMNS = [
    "minutes", "shots", "shots_on_target", "goals", "assists",
    "fouls", "fouls_drawn", "yellows", "reds", "offsides",
    "tackles", "corners_taken", "saves",
]

# Percentile at/above which a stat counts as "high" for a matchup flag.
FLAG_PERCENTILE = 0.70

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "wcbets.db"
