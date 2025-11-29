from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.core import device_service

router = APIRouter(prefix="/yachts/{yacht_id}/devices", tags=["devices"])


class UpdateStateRequest(BaseModel):
    state: bool
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


@router.post("/{device_id}/state")
def set_device_state(yacht_id: str, device_id: str, body: UpdateStateRequest):
    try:
        return device_service.set_device_state(
            yacht_id=yacht_id,
            source=body.source,
            device_id=device_id,
            state=body.state,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Device not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
