import json
from datetime import datetime
from typing import List, Dict, Any

from app.db import get_connection
from app.models import Event


class EventLogger:
    def log(self, yacht_id: str, source: str, type: str, details: Dict[str, Any]) -> Event:
        ts = datetime.utcnow().isoformat()
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO events (yacht_id, timestamp, source, type, details) "
                "VALUES (?, ?, ?, ?, ?)",
                (yacht_id, ts, source, type, json.dumps(details)),
            )
            conn.commit()
        finally:
            conn.close()

        return Event(
            yacht_id=yacht_id,
            timestamp=datetime.fromisoformat(ts),
            source=source,
            type=type,
            details=details,
        )

    def list_events(self, yacht_id: str, limit: int = 100) -> List[Event]:
        conn = get_connection()
        try:
            cur = conn.execute(
                "SELECT yacht_id, timestamp, source, type, details "
                "FROM events WHERE yacht_id = ? "
                "ORDER BY id DESC LIMIT ?",
                (yacht_id, limit),
            )
            rows = cur.fetchall()
        finally:
            conn.close()

        events: List[Event] = []
        for r in rows:
            events.append(
                Event(
                    yacht_id=r["yacht_id"],
                    timestamp=datetime.fromisoformat(r["timestamp"]),
                    source=r["source"],
                    type=r["type"],
                    details=json.loads(r["details"]),
                )
            )
        return events
