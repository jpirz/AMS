from fastapi import APIRouter, Query

from app.services.core import event_logger

router = APIRouter(prefix="/yachts/{yacht_id}/events", tags=["events"])


@router.get("/")
def list_events(yacht_id: str, limit: int = Query(100, ge=1, le=1000)):
    return event_logger.list_events(yacht_id=yacht_id, limit=limit)
