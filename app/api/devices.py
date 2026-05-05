from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import require_control_auth
from app.services.core import alarm_service, device_service, safety_service

router = APIRouter(prefix="/yachts/{yacht_id}/devices", tags=["devices"])


class UpdateStateRequest(BaseModel):
    state: Any
    source: str = "user_ui"


class ControlAuthorityRequest(BaseModel):
    authority: str
    reason: str | None = None
    source: str = "user_ui"


@router.get("/")
def list_devices(yacht_id: str):
    return device_service.list_devices(yacht_id=yacht_id)


@router.get("/{device_id}")
def get_device(yacht_id: str, device_id: str):
    try:
        return device_service.get_device(yacht_id=yacht_id, device_id=device_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Device not found")


@router.post("/{device_id}/state", dependencies=[Depends(require_control_auth)])
def set_device_state(yacht_id: str, device_id: str, body: UpdateStateRequest):
    try:
        device = device_service.set_device_state(
            yacht_id=yacht_id,
            source=body.source,
            device_id=device_id,
            state=body.state,
        )
        alarm_service.sync_device(yacht_id, device_id, device=device)
        safety_service.enforce(yacht_id)
        return device_service.get_device(yacht_id, device_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Device not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{device_id}/control", dependencies=[Depends(require_control_auth)])
def set_control_authority(yacht_id: str, device_id: str, body: ControlAuthorityRequest):
    try:
        return device_service.set_control_authority(
            yacht_id=yacht_id,
            source=body.source,
            device_id=device_id,
            authority=body.authority,
            reason=body.reason,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Device not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
