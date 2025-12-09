# app/routers/scenes.py

from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.yacht_profiles import get_scenes_for_yacht, get_devices_for_yacht
from app.routers.devices import _ensure_state_for_yacht  # share same state store

router = APIRouter(
    prefix="/yachts/{yacht_id}/scenes",
    tags=["scenes"],
)


class SceneActivateIn(BaseModel):
    source: str | None = None


@router.get("/")
async def list_scenes(yacht_id: str) -> List[Dict[str, Any]]:
    """
    Return all scenes for the given yacht.
    """
    return get_scenes_for_yacht(yacht_id)


@router.post("/{scene_id}/activate")
async def activate_scene(
    yacht_id: str,
    scene_id: str,
    body: SceneActivateIn,
) -> Dict[str, Any]:
    """
    Apply a scene: for each action in the profile, update the in-memory
    device state for this yacht.

    The UI already calls this at:
      POST /yachts/{yacht_id}/scenes/{scene_id}/activate
      body: { "source": "web_ui" }
    """
    scenes = get_scenes_for_yacht(yacht_id)
    scene = next((s for s in scenes if s.get("id") == scene_id), None)
    if not scene:
        raise HTTPException(status_code=404, detail="Unknown scene_id")

    devices = get_devices_for_yacht(yacht_id)
    valid_ids = {d["id"] for d in devices}

    state = _ensure_state_for_yacht(yacht_id)

    applied: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []

    for action in scene.get("actions", []):
        dev_id = action.get("device_id")
        target_state = action.get("state")

        if not dev_id or dev_id not in valid_ids:
            skipped.append(
                {
                    "device_id": dev_id,
                    "reason": "unknown_device",
                }
            )
            continue

        # Update the same state dict that /devices uses
        state[dev_id] = target_state
        applied.append(
            {
                "device_id": dev_id,
                "state": target_state,
            }
        )

        # TODO: here is where you would also:
        #  - write to Modbus based on device.hw_id
        #  - insert an event into your events DB

    return {
        "status": "ok",
        "yacht_id": yacht_id,
        "scene_id": scene_id,
        "applied": applied,
        "skipped": skipped,
        "source": body.source or "unknown",
    }
