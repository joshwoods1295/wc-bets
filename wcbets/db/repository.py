"""SQLite repository layer for WC Bets."""
import sqlite3
from pathlib import Path

SCHEMA = (Path(__file__).parent / "schema.sql").read_text()


def connect(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn):
    conn.executescript(SCHEMA)
    conn.commit()


def _upsert(conn, table, data, pk):
    cols = list(data.keys())
    placeholders = ",".join("?" for _ in cols)
    updates = ",".join(f"{c}=excluded.{c}" for c in cols if c != pk)
    sql = (
        f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders}) "
        f"ON CONFLICT({pk}) DO UPDATE SET {updates}"
    )
    conn.execute(sql, [data[c] for c in cols])
    conn.commit()


def upsert_player(conn, player):
    _upsert(conn, "players", player, "player_id")


def upsert_player_stats(conn, stats):
    _upsert(conn, "player_stats", stats, "player_id")


def upsert_squad_member(conn, player_id, country):
    conn.execute(
        "INSERT INTO national_squads (player_id, country) VALUES (?, ?) "
        "ON CONFLICT(player_id) DO UPDATE SET country=excluded.country",
        (player_id, country),
    )
    conn.commit()


def upsert_fixture(conn, fixture):
    _upsert(conn, "fixtures", fixture, "match_id")


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
