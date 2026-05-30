"""Scrape all WC 2026 squads from Wikipedia.

Fetches the 2026 FIFA World Cup squads page, parses every squad table,
matches players to the local DB by normalised name, and writes to
national_squads. Also patches missing positions in the players table.
"""
import unicodedata

import requests
from bs4 import BeautifulSoup

WIKI_URL = "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_squads"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; wcbets/1.0)"}

_SKIP_HEADINGS = {
    "group a", "group b", "group c", "group d", "group e", "group f",
    "group g", "group h", "group i", "group j", "group k", "group l",
    "contents", "references", "notes", "external links", "see also",
    "navigation menu", "retrieved",
}


def normalise(name):
    nfkd = unicodedata.normalize("NFKD", name or "")
    no_acc = "".join(c for c in nfkd if not unicodedata.combining(c))
    return no_acc.casefold().strip()


def _parse_pos(cell_text):
    t = cell_text.upper()
    for code in ("GK", "DF", "MF", "FW"):
        if code in t:
            return code
    return None


def _player_name(cell):
    """Strip flag icons, refs, dob brackets from a Wikipedia player td."""
    for tag in cell.find_all(["sup", "span"]):
        tag.decompose()
    name = cell.get_text(" ", strip=True)
    name = name.split("(")[0].strip()
    # Remove stray asterisks or ref numbers
    return name.strip("* \t")


def fetch_squads():
    """Return list of {country, name, position, club}."""
    r = requests.get(WIKI_URL, headers=_HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    players = []

    # Strategy: find every wikitable that looks like a squad table,
    # then look backwards to find the closest h3 (country name).
    for table in soup.find_all("table", class_="wikitable"):
        # Check this is a squad table (must have Player and Pos columns)
        ths = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        if not any("player" in h for h in ths):
            continue
        if not any("pos" in h for h in ths):
            continue

        # Find the closest preceding h3 heading
        h3 = table.find_previous("h3")
        if not h3:
            continue
        country = h3.get_text(" ", strip=True).replace("[edit]", "").strip()
        if normalise(country) in _SKIP_HEADINGS or not country:
            continue

        # Find column indices from header row
        header_cells = table.find("tr").find_all(["th", "td"])
        header_texts = [c.get_text(strip=True).lower() for c in header_cells]
        try:
            name_idx = next(i for i, h in enumerate(header_texts) if "player" in h)
            pos_idx  = next(i for i, h in enumerate(header_texts) if "pos" in h)
            club_idx = next(i for i, h in enumerate(header_texts) if "club" in h)
        except StopIteration:
            continue

        for row in table.find_all("tr")[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) <= max(name_idx, pos_idx, club_idx):
                continue
            name = _player_name(cells[name_idx])
            pos  = _parse_pos(cells[pos_idx].get_text(strip=True))
            club = cells[club_idx].get_text(" ", strip=True).split("(")[0].strip()
            if name and len(name) > 2:
                players.append({
                    "country": country,
                    "name": name,
                    "position": pos,
                    "club": club,
                })

    return players


def import_squads(conn):
    from wcbets.db import repository as repo

    print("Fetching WC 2026 squads from Wikipedia...", flush=True)
    players = fetch_squads()
    countries = {p["country"] for p in players}
    print(f"Found {len(players)} players across {len(countries)} countries.",
          flush=True)

    if not players:
        print("ERROR: Got no players. Wikipedia page structure may have changed.")
        return

    # Build name index: normalised_name -> [(player_id, minutes)]
    name_index: dict[str, list] = {}
    for pid, nm in conn.execute("SELECT player_id, name FROM players"):
        mins = conn.execute(
            "SELECT COALESCE(minutes,0) FROM player_stats WHERE player_id=?", (pid,)
        ).fetchone()
        name_index.setdefault(normalise(nm), []).append((pid, mins[0] if mins else 0))

    def find_hits(name):
        key = normalise(name)
        hits = name_index.get(key, [])
        if not hits:
            qtoks = key.split()
            if len(qtoks) >= 2:
                for db_key, entries in name_index.items():
                    ctoks = db_key.split()
                    if (len(qtoks) <= len(ctoks)
                            and all(q == c for q, c in zip(qtoks, ctoks))):
                        hits.extend(entries)
        return hits

    conn.execute("DELETE FROM national_squads")
    conn.commit()

    matched = ambiguous = unmatched = patched = 0
    for p in players:
        hits = find_hits(p["name"])
        if not hits:
            unmatched += 1
            continue
        pid = (hits[0][0] if len(hits) == 1
               else max(hits, key=lambda x: x[1])[0])
        repo.upsert_squad_member(conn, pid, p["country"])
        matched += (1 if len(hits) == 1 else 0)
        ambiguous += (1 if len(hits) > 1 else 0)

        # Patch position if DB has none
        if p["position"]:
            existing = conn.execute(
                "SELECT position FROM players WHERE player_id=?", (pid,)
            ).fetchone()
            if existing and not existing[0]:
                conn.execute("UPDATE players SET position=? WHERE player_id=?",
                             (p["position"], pid))
                patched += 1
    conn.commit()

    print(f"\n  ✅ Matched (unique)    : {matched}")
    print(f"  ✅ Resolved (max mins) : {ambiguous}")
    print(f"  ⚠️  Not in Big-5 DB    : {unmatched}")
    if patched:
        print(f"  📍 Positions patched  : {patched}")
    print(f"\nSquads in database ({len(countries)} countries):")
    for country, count in conn.execute(
        "SELECT country, COUNT(*) FROM national_squads "
        "GROUP BY country ORDER BY country"
    ):
        print(f"  {country}: {count} players")
