from wcbets.analysis.percentiles import percentile_rank


def test_percentile_rank_middle():
    peers = [1.0, 2.0, 3.0, 4.0, 5.0]
    # value 4.0: 3 of 5 peers are <= it... use fraction strictly below + equal/2
    r = percentile_rank(4.0, peers)
    assert 0.6 <= r <= 0.8


def test_percentile_rank_max_is_one():
    assert percentile_rank(5.0, [1.0, 2.0, 5.0]) == 1.0


def test_percentile_rank_empty_peers_is_zero():
    assert percentile_rank(3.0, []) == 0.0
