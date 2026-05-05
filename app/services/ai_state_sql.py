import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.db import get_connection


class AIStateService:
    def add_log(
        self,
        yacht_id: str,
        generated_at: datetime,
        summary: str,
        actions: List[Dict[str, Any]],
        mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        conn = get_connection()
        try:
            cur = conn.execute(
                "INSERT INTO ai_logs "
                "(yacht_id, generated_at, summary, actions_json, mode) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    yacht_id,
                    generated_at.isoformat(),
                    summary,
                    json.dumps(actions),
                    mode,
                ),
            )
            conn.commit()
            log_id = cur.lastrowid
        finally:
            conn.close()

        return {
            "id": str(log_id),
            "generated_at": generated_at,
            "summary": summary,
            "actions": actions,
            "mode": mode,
        }

    def list_logs(self, yacht_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT id, generated_at, summary, actions_json, mode "
                "FROM ai_logs WHERE yacht_id = ? ORDER BY id DESC LIMIT ?",
                (yacht_id, limit),
            ).fetchall()
        finally:
            conn.close()

        logs: List[Dict[str, Any]] = []
        for row in rows:
            logs.append(
                {
                    "id": str(row["id"]),
                    "generated_at": datetime.fromisoformat(row["generated_at"]),
                    "summary": row["summary"],
                    "actions": json.loads(row["actions_json"]),
                    "mode": row["mode"],
                }
            )
        return logs

    def get_occupancy(self, yacht_id: str) -> str:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT occupancy FROM ai_occupancy WHERE yacht_id = ?",
                (yacht_id,),
            ).fetchone()
        finally:
            conn.close()

        return row["occupancy"] if row else "unknown"

    def set_occupancy(self, yacht_id: str, occupancy: str) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO ai_occupancy (yacht_id, occupancy, updated_at) "
                "VALUES (?, ?, ?) "
                "ON CONFLICT(yacht_id) DO UPDATE SET "
                "occupancy = excluded.occupancy, updated_at = excluded.updated_at",
                (yacht_id, occupancy, now.isoformat()),
            )
            conn.commit()
        finally:
            conn.close()

        return {
            "status": "ok",
            "yacht_id": yacht_id,
            "occupancy": occupancy,
            "updated_at": now.isoformat(),
        }
