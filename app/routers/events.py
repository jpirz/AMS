# app/routers/events.py

from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Deque, Dict, Any, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(
    prefix="/yachts/{yacht_id}/events",
    tags=["events"],
)


class Event(BaseModel):
    timestamp: datetime
    type: str
    source: str
    details: Optional[Dict[str, Any]] = None


# In-memory event storage per yacht_id
EVENTS: Dict[str, Deque[Event]] = defaultdict(lambda: deque(maxlen=500))


def record_event(
    yacht_id: str,
    event_type: str,
    source: str,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Helper used by other routers (devices, scenes, etc.) to log events.

    - Stores them in memory per-yacht.
    - UI reads them via GET /yachts/{yacht_id}/events?limit=...
    """
    ev = Event(
      timestamp=datetime.now(timezone.utc),
      type=event_type,
      source=source,
      details=details or {},
    )
    EVENTS[yacht_id].appendleft(ev)


@router.get("/")
async def list_events(yacht_id: str, limit: int = 50) -> List[Event]:
    """
    Return most recent events for a yacht, newest first.
    UI calls this as /events?limit=50 (FastAPI will 307 -> /events/).
    """
    events = list(EVENTS[yacht_id])[:limit]
    return events
