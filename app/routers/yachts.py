import json
from typing import Any, Dict, List

from fastapi import APIRouter

from app.db import get_connection
from app.yacht_profiles import list_known_yachts, get_yacht_meta

router = APIRouter(
    prefix="/yachts",
    tags=["yachts"],
)


@router.get("/")
async def list_yachts() -> List[Dict[str, Any]]:
    """
    List yachts provisioned in SQLite, falling back to static profiles.
    Useful for a future 'boat selector' in the UI.
    """
    conn = get_connection()
    try:
        rows = conn.execute("SELECT id, name FROM yachts ORDER BY name ASC").fetchall()
    finally:
        conn.close()

    if rows:
        return [{"id": row["id"], "name": row["name"]} for row in rows]

    return list_known_yachts()


@router.get("/{yacht_id}/meta")
async def yacht_meta(yacht_id: str) -> Dict[str, Any]:
    """
    Basic metadata + hardware config for a given yacht.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, name, hardware_json FROM yachts WHERE id = ?",
            (yacht_id,),
        ).fetchone()
    finally:
        conn.close()

    if row:
        hardware = json.loads(row["hardware_json"]) if row["hardware_json"] else {}
        return {
            "id": row["id"],
            "name": row["name"],
            "hardware": hardware,
        }

    return get_yacht_meta(yacht_id)
