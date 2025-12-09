# app/routers/devices.py

from typing import Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.yacht_profiles import get_devices_for_yacht
from app.routers.events import record_event

router = APIRouter(
    prefix="/yachts/{yacht_id}/devices",
    tags=["devices"],
)

# In-memory state per yacht_id & per device_id
DEVICE_STATE: Dict[str, Dict[str, Any]] = {}


def _ensure_state_for_yacht(yacht_id: str) -> Dict[str, Any]:
    """
    Initialise per-yacht device state the first time we see that yacht.
    """
    if yacht_id not in DEVICE_STATE:
        devices = get_devices_for_yacht(yacht_id)
        DEVICE_STATE[yacht_id] = {d["id"]: False for d in devices}
    return DEVICE_STATE[yacht_id]


@router.get("/")
async def list_devices(yacht_id: str):
    devices = get_devices_for_yacht(yacht_id)
    state = _ensure_state_for_yacht(yacht_id)

    # merge definition + state
    out = []
    for d in devices:
        d_copy = dict(d)
        d_copy["state"] = state.get(d["id"])
        out.append(d_copy)
    return out


class DeviceStateIn(BaseModel):
    state: Any
    source: str | None = None


@router.post("/{device_id}/state")
async def set_device_state(yacht_id: str, device_id: str, body: DeviceStateIn):
    devices = get_devices_for_yacht(yacht_id)
    dev_ids = {d["id"] for d in devices}
    if device_id not in dev_ids:
        raise HTTPException(status_code=404, detail="Unknown device_id")

    state = _ensure_state_for_yacht(yacht_id)
    state[device_id] = body.state

    # Log event for history / alarms UI
    record_event(
        yacht_id=yacht_id,
        event_type="device_state_changed",
        source=body.source or "web_ui",
        details={
            "device_id": device_id,
            "new_state": body.state,
        },
    )

    # TODO: here you also write to Modbus (coil/holding register) based on device.hw_id

    return {
        "status": "ok",
        "yacht_id": yacht_id,
        "device_id": device_id,
        "state": body.state,
    }
