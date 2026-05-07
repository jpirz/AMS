import json
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.db import get_connection


class HardwareStatusService:
    def record_ok(self, yacht_id: str, hw_id: str, value: Any = None) -> None:
        self._record(yacht_id, hw_id, "ok", value=value)

    def record_error(self, yacht_id: str, hw_id: str, error: str, value: Any = None) -> None:
        self._record(yacht_id, hw_id, "error", error=error, value=value)

    def list_status(self, yacht_id: str) -> List[Dict[str, Any]]:
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT hw_id, status, last_checked_at, last_error, last_value "
                "FROM hardware_status WHERE yacht_id = ? ORDER BY hw_id ASC",
                (yacht_id,),
            ).fetchall()
        finally:
            conn.close()

        return [
            {
                "hw_id": row["hw_id"],
                "status": row["status"],
                "last_checked_at": row["last_checked_at"],
                "last_error": row["last_error"],
                "last_value": json.loads(row["last_value"]) if row["last_value"] is not None else None,
            }
            for row in rows
        ]

    def health_summary(self, yacht_id: str) -> Dict[str, Any]:
        statuses = self.list_status(yacht_id)
        errors = [s for s in statuses if s["status"] != "ok"]
        return {
            "yacht_id": yacht_id,
            "status": "error" if errors else "ok",
            "checked_points": len(statuses),
            "errors": errors,
            "points": statuses,
        }

    def _record(
        self,
        yacht_id: str,
        hw_id: str,
        status: str,
        error: str | None = None,
        value: Any = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO hardware_status "
                "(yacht_id, hw_id, status, last_checked_at, last_error, last_value) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(yacht_id, hw_id) DO UPDATE SET "
                "status = excluded.status, last_checked_at = excluded.last_checked_at, "
                "last_error = excluded.last_error, last_value = excluded.last_value",
                (yacht_id, hw_id, status, now, error, json.dumps(value)),
            )
            conn.commit()
        finally:
            conn.close()
