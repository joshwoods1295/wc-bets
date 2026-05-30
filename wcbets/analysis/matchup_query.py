"""DB-backed helpers that feed the matchup engine. Read-only queries."""
from wcbets.analysis.normalise import per90_row
from wcbets.config import STAT_COLUMNS

_P90_KEYS = [c for c in STAT_COLUMNS if c != "minutes"]


def _row_to_player(row, cols):
    d = dict(zip(cols, row))
    return per90_row(d, _P90_KEYS)


def players_by_country(conn, country):
    cols = ["player_id", "name", "position"] + STAT_COLUMNS
    sql = f"""
        SELECT p.player_id, p.name, p.position, {', '.join('s.'+c for c in STAT_COLUMNS)}
        FROM players p
        JOIN national_squads ns ON ns.player_id = p.player_id
        JOIN player_stats s ON s.player_id = p.player_id
        WHERE ns.country = ?
    """
    return [_row_to_player(r, cols) for r in conn.execute(sql, (country,))]


def peer_distribution(conn, position, p90_key):
    base = p90_key[:-4] if p90_key.endswith("_p90") else p90_key
    cols = ["player_id", "name", "position"] + STAT_COLUMNS
    sql = f"""
        SELECT p.player_id, p.name, p.position, {', '.join('s.'+c for c in STAT_COLUMNS)}
        FROM players p JOIN player_stats s ON s.player_id = p.player_id
        WHERE p.position = ?
    """
    out = []
    for r in conn.execute(sql, (position,)):
        out.append(_row_to_player(r, cols)[p90_key])
    return out


def list_countries(conn):
    return [r[0] for r in conn.execute(
        "SELECT DISTINCT country FROM national_squads ORDER BY country")]
