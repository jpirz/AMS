import sqlite3
from pathlib import Path

DB_PATH = Path("yachtos.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    schema = """
    CREATE TABLE IF NOT EXISTS yachts (
        id            TEXT PRIMARY KEY,
        name          TEXT NOT NULL,
        hardware_json TEXT
    );

    CREATE TABLE IF NOT EXISTS devices (
        yacht_id             TEXT NOT NULL,
        id                   TEXT NOT NULL,
        name                 TEXT NOT NULL,
        zone                 TEXT NOT NULL,
        type                 TEXT NOT NULL,
        state                TEXT,
        hw_id                TEXT,
        ai_control           TEXT NOT NULL,
        max_runtime_seconds  INTEGER,
        requires_human_ack   INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (yacht_id, id),
        FOREIGN KEY (yacht_id) REFERENCES yachts(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS scenes (
        yacht_id    TEXT NOT NULL,
        id          TEXT NOT NULL,
        name        TEXT NOT NULL,
        description TEXT,
        PRIMARY KEY (yacht_id, id),
        FOREIGN KEY (yacht_id) REFERENCES yachts(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS scene_actions (
        yacht_id    TEXT NOT NULL,
        scene_id    TEXT NOT NULL,
        order_index INTEGER NOT NULL,
        device_id   TEXT NOT NULL,
        state       TEXT NOT NULL,
        PRIMARY KEY (yacht_id, scene_id, order_index),
        FOREIGN KEY (yacht_id, scene_id) REFERENCES scenes(yacht_id, id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS events (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        yacht_id  TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        source    TEXT NOT NULL,
        type      TEXT NOT NULL,
        details   TEXT NOT NULL,
        FOREIGN KEY (yacht_id) REFERENCES yachts(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS system_state (
        yacht_id TEXT PRIMARY KEY,
        ai_mode  TEXT NOT NULL,
        FOREIGN KEY (yacht_id) REFERENCES yachts(id) ON DELETE CASCADE
    );
    """
    conn = get_connection()
    try:
        conn.executescript(schema)
        conn.commit()
    finally:
        conn.close()
