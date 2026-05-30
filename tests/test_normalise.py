from wcbets.analysis.normalise import per90


def test_per90_basic():
    # 9 fouls in 180 minutes -> 4.5 per 90
    assert per90(9, 180) == 4.5


def test_per90_zero_minutes_is_zero():
    assert per90(5, 0) == 0.0


def test_per90_row_adds_suffixed_keys():
    from wcbets.analysis.normalise import per90_row
    row = {"minutes": 90, "fouls": 2, "tackles": 3}
    out = per90_row(row, ["fouls", "tackles"])
    assert out["fouls_p90"] == 2.0
    assert out["tackles_p90"] == 3.0
    assert out["fouls"] == 2  # original preserved
