from typing import Optional

from fastapi import APIRouter, Query

from app.services.core import event_logger

router = APIRouter(prefix="/yachts/{yacht_id}/events", tags=["events"])


@router.get("/")
def list_events(
    yacht_id: str,
    limit: int = Query(100, ge=1, le=1000),
    type: Optional[str] = None,
    source: Optional[str] = None,
    device_id: Optional[str] = None,
    q: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    return event_logger.list_events(
        yacht_id=yacht_id,
        limit=limit,
        type=type,
        source=source,
        device_id=device_id,
        q=q,
        date_from=date_from,
        date_to=date_to,
    )
