import json
from datetime import datetime
from typing import List, Dict, Any, Optional

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

    def list_events(
        self,
        yacht_id: str,
        limit: int = 100,
        type: Optional[str] = None,
        source: Optional[str] = None,
        device_id: Optional[str] = None,
        q: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> List[Event]:
        where = ["yacht_id = ?"]
        params: list[Any] = [yacht_id]

        if type:
            where.append("type = ?")
            params.append(type)
        if source:
            where.append("source = ?")
            params.append(source)
        if date_from:
            where.append("timestamp >= ?")
            params.append(date_from)
        if date_to:
            where.append("timestamp <= ?")
            params.append(date_to)
        if device_id:
            where.append("details LIKE ?")
            params.append(f'%"device_id": "{device_id}"%')
        if q:
            where.append("(type LIKE ? OR source LIKE ? OR details LIKE ?)")
            needle = f"%{q}%"
            params.extend([needle, needle, needle])

        params.append(limit)
        conn = get_connection()
        try:
            cur = conn.execute(
                "SELECT yacht_id, timestamp, source, type, details "
                f"FROM events WHERE {' AND '.join(where)} "
                "ORDER BY id DESC LIMIT ?",
                params,
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
