"""Matchup flag engine. Pure functions over plain dicts.

A 'rule' pairs a defender stat with an attacker stat. A flag fires when BOTH
players sit at or above the percentile threshold for their respective stat,
relative to positional peers supplied by the caller.
"""
from wcbets.analysis.percentiles import percentile_rank

# (label, defender_stat, attacker_stat)
RULES = [
    ("High-fouling defender vs high fouls-drawn attacker",
     "fouls_p90", "fouls_drawn_p90"),
]


def evaluate_matchup(defender, attacker, peers, threshold=0.80):
    flags = []
    for label, def_stat, atk_stat in RULES:
        def_val = defender.get(def_stat, 0.0)
        atk_val = attacker.get(atk_stat, 0.0)
        def_pct = percentile_rank(def_val, peers.get(f"defender_{def_stat}", []))
        atk_pct = percentile_rank(atk_val, peers.get(f"attacker_{atk_stat}", []))
        if def_pct >= threshold and atk_pct >= threshold:
            flags.append({
                "label": label,
                "defender": defender.get("name"),
                "attacker": attacker.get("name"),
                "defender_stat": def_stat,
                "attacker_stat": atk_stat,
                "defender_value": def_val,
                "attacker_value": atk_val,
                "defender_pct": def_pct,
                "attacker_pct": atk_pct,
            })
    return flags
