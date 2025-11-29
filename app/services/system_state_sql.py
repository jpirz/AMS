from app.db import get_connection
from app.models import AiMode


class SystemState:
    def get_ai_mode(self, yacht_id: str) -> AiMode:
        conn = get_connection()
        try:
            cur = conn.execute(
                "SELECT ai_mode FROM system_state WHERE yacht_id = ?",
                (yacht_id,),
            )
            row = cur.fetchone()
        finally:
            conn.close()

        if row is None:
            return AiMode.MONITOR

        return AiMode(row["ai_mode"])

    def set_ai_mode(self, yacht_id: str, mode: AiMode):
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO system_state (yacht_id, ai_mode) "
                "VALUES (?, ?) "
                "ON CONFLICT(yacht_id) DO UPDATE SET ai_mode = excluded.ai_mode",
                (yacht_id, mode.value),
            )
            conn.commit()
        finally:
            conn.close()
