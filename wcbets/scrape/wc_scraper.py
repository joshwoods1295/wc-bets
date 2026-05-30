"""World Cup squad/fixture mapping helpers.

Automated WC scraping is not available: soccerdata's FBref backend does not
expose international tournaments, and final squads are published only just
before the tournament. The supported path is the manual CSV import in
``wcbets.scrape.manual_import`` (templates live in ``data/templates/``).

The name-reconciliation helpers below are pure and unit-tested; they exist to
match imported squad members to league players by normalised name when a CSV
provides names rather than our ``<league>:<name>`` player ids.
"""
import unicodedata

_WC_UNAVAILABLE = (
    "Automated World Cup squad/fixture scraping is not available: soccerdata's "
    "FBref backend does not expose international tournaments, and WC 2026 squads "
    "are not published until just before the tournament. Use the manual CSV "
    "import instead: wcbets.scrape.manual_import.import_squads(conn, 'squads.csv') "
    "and import_fixtures(conn, 'fixtures.csv'). See data/templates/ for templates."
)


def normalise_name(name):
    """Lowercase, accent-stripped form for matching player names across sources."""
    nfkd = unicodedata.normalize("NFKD", name or "")
    no_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    return no_accents.casefold().strip()


def match_player(norm_name, players):
    """Return the player_id whose name normalises to ``norm_name``, or None."""
    for p in players:
        if normalise_name(p["name"]) == norm_name:
            return p["player_id"]
    return None


def scrape_squads(conn, country, fbref_team_id):
    """Not available — see manual_import. Kept for API symmetry."""
    raise NotImplementedError(_WC_UNAVAILABLE)


def scrape_fixtures(conn):
    """Not available — see manual_import. Kept for API symmetry."""
    raise NotImplementedError(_WC_UNAVAILABLE)
