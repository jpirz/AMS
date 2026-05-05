from datetime import datetime, timezone
from typing import Dict

from app.db import get_connection
from app.services.event_service_sql import EventLogger


VALID_MODES = {"in_port", "at_anchor", "underway", "unattended"}


class VesselStateService:
    def __init__(self, event_logger: EventLogger):
        self.events = event_logger

    def get_mode(self, yacht_id: str) -> str:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT mode FROM vessel_state WHERE yacht_id = ?",
                (yacht_id,),
            ).fetchone()
        finally:
            conn.close()

        return row["mode"] if row else "in_port"

    def set_mode(self, yacht_id: str, mode: str, source: str = "user_ui") -> Dict[str, str]:
        if mode not in VALID_MODES:
            raise ValueError("Invalid vessel mode")

        now = datetime.now(timezone.utc).isoformat()
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO vessel_state (yacht_id, mode, updated_at) "
                "VALUES (?, ?, ?) "
                "ON CONFLICT(yacht_id) DO UPDATE SET "
                "mode = excluded.mode, updated_at = excluded.updated_at",
                (yacht_id, mode, now),
            )
            conn.commit()
        finally:
            conn.close()

        self.events.log(
            yacht_id=yacht_id,
            source=source,
            type="vessel_mode_change",
            details={"mode": mode},
        )
        return {"yacht_id": yacht_id, "mode": mode, "updated_at": now}
