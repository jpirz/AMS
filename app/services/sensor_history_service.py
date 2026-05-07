import json
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.db import get_connection


class SensorHistoryService:
    def record(self, yacht_id: str, device_id: str, state: Any, source: str) -> None:
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO sensor_history (yacht_id, device_id, timestamp, state, source) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    yacht_id,
                    device_id,
                    datetime.now(timezone.utc).isoformat(),
                    json.dumps(state),
                    source,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def list_history(self, yacht_id: str, device_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT device_id, timestamp, state, source "
                "FROM sensor_history WHERE yacht_id = ? AND device_id = ? "
                "ORDER BY id DESC LIMIT ?",
                (yacht_id, device_id, limit),
            ).fetchall()
        finally:
            conn.close()

        return [
            {
                "device_id": row["device_id"],
                "timestamp": row["timestamp"],
                "state": json.loads(row["state"]),
                "source": row["source"],
            }
            for row in rows
        ]

    def latest_by_sensor(self, yacht_id: str, limit_per_sensor: int = 1) -> List[Dict[str, Any]]:
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT h.device_id, h.timestamp, h.state, h.source "
                "FROM sensor_history h "
                "JOIN ("
                "  SELECT device_id, MAX(id) AS max_id "
                "  FROM sensor_history WHERE yacht_id = ? GROUP BY device_id"
                ") latest ON latest.max_id = h.id "
                "ORDER BY h.device_id ASC",
                (yacht_id,),
            ).fetchall()
        finally:
            conn.close()

        return [
            {
                "device_id": row["device_id"],
                "timestamp": row["timestamp"],
                "state": json.loads(row["state"]),
                "source": row["source"],
            }
            for row in rows[:limit_per_sensor * max(len(rows), 1)]
        ]
