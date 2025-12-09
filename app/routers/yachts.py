# app/routers/yachts.py

from fastapi import APIRouter, HTTPException

router = APIRouter(
    prefix="/yachts",
    tags=["yachts"],
)

# For now this is a simple in-code registry.
# It lines up with the JSON you pasted: id + name.
YACHTS = {
    "marex-21-001": {
      "id": "marex-21-001",
      "name": "Marex Flexi 21 #001",
    },
    # Later you can add more:
    # "sealine-25-001": {"id": "sealine-25-001", "name": "Sealine 25 #001"},
}


@router.get("/", summary="List configured yachts")
async def list_yachts():
    """
    Used by the web UI to populate the boat selector.
    """
    return list(YACHTS.values())


@router.get("/{yacht_id}/meta", summary="Get metadata for a single yacht")
async def yacht_meta(yacht_id: str):
    """
    Basic metadata; used by UI for titles, etc.
    """
    yacht = YACHTS.get(yacht_id)
    if not yacht:
        raise HTTPException(status_code=404, detail="Unknown yacht_id")
    return yacht
