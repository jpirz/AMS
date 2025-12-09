# app/routers/yachts.py

from typing import List, Dict, Any
from fastapi import APIRouter

from app.yacht_profiles import list_known_yachts, get_yacht_meta

router = APIRouter(
    prefix="/yachts",
    tags=["yachts"],
)


@router.get("/")
async def list_yachts() -> List[Dict[str, Any]]:
    """
    List all explicitly configured yachts (from PROFILES).
    Useful for a future 'boat selector' in the UI.
    """
    return list_known_yachts()


@router.get("/{yacht_id}/meta")
async def yacht_meta(yacht_id: str) -> Dict[str, Any]:
    """
    Basic metadata + hardware config for a given yacht.
    """
    return get_yacht_meta(yacht_id)
