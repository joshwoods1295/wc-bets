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
    updates = ", ".join(f"{c}=excluded.{c}" for c in cols if c not in pk_cols)
    sql = (f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) "
           f"ON CONFLICT({', '.join(pk_cols)}) DO UPDATE SET {updates}")
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
