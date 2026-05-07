import sqlite3
import os
from pathlib import Path

DB_PATH = Path(os.getenv("YACHTOS_DB_PATH", "yachtos.db"))


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
        control_authority    TEXT NOT NULL DEFAULT 'ai_allowed',
        control_reason       TEXT,
        last_changed_at      TEXT,
        last_changed_by      TEXT,
        current_on_since     TEXT,
        total_runtime_seconds INTEGER NOT NULL DEFAULT 0,
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

    CREATE TABLE IF NOT EXISTS vessel_state (
        yacht_id   TEXT PRIMARY KEY,
        mode       TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (yacht_id) REFERENCES yachts(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS ai_logs (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        yacht_id     TEXT NOT NULL,
        generated_at TEXT NOT NULL,
        summary      TEXT NOT NULL,
        actions_json TEXT NOT NULL,
        mode         TEXT,
        FOREIGN KEY (yacht_id) REFERENCES yachts(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS ai_occupancy (
        yacht_id    TEXT PRIMARY KEY,
        occupancy   TEXT NOT NULL,
        updated_at  TEXT NOT NULL,
        FOREIGN KEY (yacht_id) REFERENCES yachts(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS users (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        username      TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role          TEXT NOT NULL,
        created_at    TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS auth_sessions (
        token      TEXT PRIMARY KEY,
        user_id    INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS sensor_history (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        yacht_id  TEXT NOT NULL,
        device_id TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        state     TEXT NOT NULL,
        source    TEXT NOT NULL,
        FOREIGN KEY (yacht_id, device_id) REFERENCES devices(yacht_id, id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS hardware_status (
        yacht_id       TEXT NOT NULL,
        hw_id          TEXT NOT NULL,
        status         TEXT NOT NULL,
        last_checked_at TEXT NOT NULL,
        last_error     TEXT,
        last_value     TEXT,
        PRIMARY KEY (yacht_id, hw_id),
        FOREIGN KEY (yacht_id) REFERENCES yachts(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS alarms (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        yacht_id         TEXT NOT NULL,
        alarm_key        TEXT NOT NULL,
        device_id        TEXT NOT NULL,
        name             TEXT NOT NULL,
        zone             TEXT,
        severity         TEXT NOT NULL,
        status           TEXT NOT NULL,
        state            TEXT,
        first_raised_at  TEXT NOT NULL,
        last_changed_at  TEXT NOT NULL,
        acknowledged_at  TEXT,
        cleared_at       TEXT,
        details          TEXT NOT NULL,
        FOREIGN KEY (yacht_id) REFERENCES yachts(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_events_yacht_id_id
        ON events(yacht_id, id DESC);

    CREATE INDEX IF NOT EXISTS idx_ai_logs_yacht_id_id
        ON ai_logs(yacht_id, id DESC);

    CREATE INDEX IF NOT EXISTS idx_sensor_history_yacht_device_id
        ON sensor_history(yacht_id, device_id, id DESC);

    CREATE INDEX IF NOT EXISTS idx_sessions_user_id
        ON auth_sessions(user_id);

    CREATE UNIQUE INDEX IF NOT EXISTS idx_alarms_active_key
        ON alarms(yacht_id, alarm_key)
        WHERE status = 'active';

    CREATE INDEX IF NOT EXISTS idx_alarms_yacht_changed
        ON alarms(yacht_id, last_changed_at DESC);
    """
    conn = get_connection()
    try:
        conn.executescript(schema)
        _ensure_column(conn, "devices", "control_authority", "TEXT NOT NULL DEFAULT 'ai_allowed'")
        _ensure_column(conn, "devices", "control_reason", "TEXT")
        _ensure_column(conn, "devices", "last_changed_at", "TEXT")
        _ensure_column(conn, "devices", "last_changed_by", "TEXT")
        _ensure_column(conn, "devices", "current_on_since", "TEXT")
        _ensure_column(conn, "devices", "total_runtime_seconds", "INTEGER NOT NULL DEFAULT 0")
        conn.commit()
    finally:
        conn.close()


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
