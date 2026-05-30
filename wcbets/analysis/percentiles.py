"""Rank a player's stat against positional peers. Pure functions."""


def percentile_rank(value, peers):
    """Fraction of peers with value <= the given value (0..1)."""
    if not peers:
        return 0.0
    at_or_below = sum(1 for p in peers if p <= value)
    return round(at_or_below / len(peers), 4)
