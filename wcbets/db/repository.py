"""The only module that talks to SQLite."""
import sqlite3
from pathlib import Path

_SCHEMA = Path(__file__).with_name("schema.sql")


def connect(db_path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA.read_text())
    conn.commit()


def _upsert(conn, table, row, pk_cols):
    cols = list(row)
    placeholders = ", ".join("?" for _ in cols)
    non_pk = [c for c in cols if c not in pk_cols]
    if non_pk:
        updates = ", ".join(f"{c}=excluded.{c}" for c in non_pk)
        conflict = f"ON CONFLICT({', '.join(pk_cols)}) DO UPDATE SET {updates}"
    else:
        # Every column is part of the PK (e.g. national_squads): nothing to
        # update on conflict, so make the upsert a no-op instead of emitting
        # an invalid `DO UPDATE SET` with no assignments.
        conflict = f"ON CONFLICT({', '.join(pk_cols)}) DO NOTHING"
    sql = (f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) "
           + conflict)
    conn.execute(sql, [row[c] for c in cols])
    conn.commit()


def upsert_player(conn, row):
    _upsert(conn, "players", row, ["player_id"])


def upsert_player_stats(conn, row):
    _upsert(conn, "player_stats", row, ["player_id", "season"])


def upsert_squad_member(conn, player_id, country):
    _upsert(conn, "national_squads",
            {"player_id": player_id, "country": country},
            ["player_id", "country"])


def upsert_fixture(conn, row):
    _upsert(conn, "fixtures", row, ["match_id"])


SEED_BACKLOG = [
    "ML projections of player stats",
    "Bookmaker-odds ingestion and +EV value detection",
    "Real-time / in-play data",
]


def add_backlog_item(conn, title, notes="", now=None):
    cur = conn.execute(
        "INSERT INTO backlog (title, notes, status, created_at) "
        "VALUES (?, ?, 'open', ?)", (title, notes, now or ""))
    conn.commit()
    return cur.lastrowid


def list_backlog(conn):
    rows = conn.execute(
        "SELECT id, title, notes, status, created_at FROM backlog ORDER BY id")
    cols = ["id", "title", "notes", "status", "created_at"]
    return [dict(zip(cols, r)) for r in rows]


def complete_backlog_item(conn, item_id):
    conn.execute("UPDATE backlog SET status='done' WHERE id=?", (item_id,))
    conn.commit()


def seed_backlog(conn, now=None):
    existing = {i["title"] for i in list_backlog(conn)}
    for title in SEED_BACKLOG:
        if title not in existing:
            add_backlog_item(conn, title, now=now)
