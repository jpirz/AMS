import json
from typing import Any, Dict

from fastapi import APIRouter, Depends

from app.auth import require_admin_auth
from app.db import get_connection

router = APIRouter(prefix="/yachts/{yacht_id}/export", tags=["export"])


TABLES = [
    "yachts",
    "devices",
    "scenes",
    "scene_actions",
    "events",
    "system_state",
    "vessel_state",
    "ai_logs",
    "ai_occupancy",
    "alarms",
    "sensor_history",
    "hardware_status",
]


@router.get("/json", dependencies=[Depends(require_admin_auth)])
def export_yacht(yacht_id: str) -> Dict[str, Any]:
    conn = get_connection()
    try:
        data: Dict[str, Any] = {"yacht_id": yacht_id, "tables": {}}
        for table in TABLES:
            if table == "yachts":
                rows = conn.execute("SELECT * FROM yachts WHERE id = ?", (yacht_id,)).fetchall()
            else:
                rows = conn.execute(
                    f"SELECT * FROM {table} WHERE yacht_id = ?",
                    (yacht_id,),
                ).fetchall()
            data["tables"][table] = [_decode_row(dict(row)) for row in rows]
    finally:
        conn.close()
    return data


def _decode_row(row: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in list(row.items()):
        if isinstance(value, str) and key.endswith(("_json", "details", "state", "actions_json", "last_value")):
            try:
                row[key] = json.loads(value)
            except json.JSONDecodeError:
                pass
    return row
