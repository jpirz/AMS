from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.auth import require_control_auth
from app.services.core import alarm_service

router = APIRouter(prefix="/yachts/{yacht_id}/alarms", tags=["alarms"])


@router.get("/active")
def active_alarms(yacht_id: str):
    return alarm_service.active_alarms(yacht_id)


@router.get("/history")
def alarm_history(yacht_id: str, limit: int = Query(100, ge=1, le=500)):
    return alarm_service.alarm_history(yacht_id, limit=limit)


class AlarmActionRequest(BaseModel):
    source: str = "user_ui"


@router.post("/acknowledge", dependencies=[Depends(require_control_auth)])
def acknowledge_alarms(yacht_id: str, body: AlarmActionRequest | None = None):
    source = body.source if body else "user_ui"
    return alarm_service.acknowledge_active(yacht_id, source=source)


@router.post("/clear-cleared", dependencies=[Depends(require_control_auth)])
def clear_cleared_alarms(yacht_id: str, body: AlarmActionRequest | None = None):
    source = body.source if body else "user_ui"
    return alarm_service.clear_cleared(yacht_id, source=source)
