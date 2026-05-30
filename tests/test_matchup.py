from wcbets.analysis.matchup import evaluate_matchup


def test_high_fouler_vs_high_fouls_drawn_flags():
    # defender fouls a lot; attacker draws a lot of fouls
    defender = {"name": "LB", "fouls_p90": 2.5}
    attacker = {"name": "RW", "fouls_drawn_p90": 3.0}
    peers = {
        "defender_fouls_p90": [0.5, 1.0, 1.2, 1.5, 2.5],   # 2.5 -> 1.0 pct
        "attacker_fouls_drawn_p90": [0.5, 1.0, 1.5, 2.0, 3.0],  # 3.0 -> 1.0 pct
    }
    flags = evaluate_matchup(defender, attacker, peers, threshold=0.80)
    assert any("foul" in f["label"].lower() for f in flags)
    flag = flags[0]
    assert flag["defender_pct"] == 1.0
    assert flag["attacker_pct"] == 1.0


def test_no_flag_when_below_threshold():
    defender = {"name": "LB", "fouls_p90": 0.5}
    attacker = {"name": "RW", "fouls_drawn_p90": 0.5}
    peers = {
        "defender_fouls_p90": [0.5, 1.0, 1.2, 1.5, 2.5],
        "attacker_fouls_drawn_p90": [0.5, 1.0, 1.5, 2.0, 3.0],
    }
    flags = evaluate_matchup(defender, attacker, peers, threshold=0.80)
    assert flags == []
