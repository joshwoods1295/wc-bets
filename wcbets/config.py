"""Central config: scope, paths, and flag thresholds."""
from pathlib import Path

# Leagues in scope (soccerdata FBref league IDs).
# soccerdata only exposes the Big 5 for player-season stats.
LEAGUES = [
    "ENG-Premier League",
    "ESP-La Liga",
    "ITA-Serie A",
    "GER-Bundesliga",
    "FRA-Ligue 1",
]

# Season in soccerdata format (e.g. "2024" means 2024-25).
SEASON = "2024"

# Stats we store (all bettable markets). Keys are our canonical column names.
STAT_COLUMNS = [
    "minutes", "shots", "shots_on_target", "goals", "assists",
    "fouls", "fouls_drawn", "yellows", "reds", "offsides",
    "tackles", "corners_taken", "saves",
]

# Percentile at/above which a stat counts as "high" for a matchup flag.
FLAG_PERCENTILE = 0.80

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "wcbets.db"
