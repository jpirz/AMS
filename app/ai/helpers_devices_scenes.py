# app/ai/helpers_devices_scenes.py

"""
Thin helper layer for the AI/watchkeeper to interact with devices and scenes
using your existing services.

⚠️ IMPORTANT:
- This does NOT change any behaviour.
- It just forwards calls into DeviceService and SceneService.
"""

from typing import List, Any

from app.models import Device, Scene
from app.services.device_service_sql import DeviceService
from app.services.scene_service_sql import SceneService


# -------- DEVICES -----------------------------------------------------------

async def get_devices_for_yacht(
    yacht_id: str,
    device_service: DeviceService,
) -> List[Device]:
    """
    Return the current devices for a yacht.

    This just wraps DeviceService.list_devices so the AI code has a clean
    function to call.
    """
    # DeviceService is synchronous; calling it directly here is fine.
    return device_service.list_devices(yacht_id)


async def set_device_state_internal(
    yacht_id: str,
    device_id: str,
    state: Any,
    source: str,
    device_service: DeviceService,
) -> Device:
    """
    Set a device state via the same path your API uses.

    This calls DeviceService.set_device_state, which:
      - validates type vs state
      - writes to hardware (via HardwareManager)
      - updates the DB
      - logs an event via EventLogger
    """
    device = device_service.set_device_state(
        yacht_id=yacht_id,
        source=source,
        device_id=device_id,
        state=state,
    )
    return device


# -------- SCENES ------------------------------------------------------------

async def list_scenes_for_yacht(
    yacht_id: str,
    scene_service: SceneService,
) -> List[Scene]:
    """
    List scenes for a yacht.

    Just wraps SceneService.list_scenes.
    """
    return scene_service.list_scenes(yacht_id)


async def activate_scene_internal(
    yacht_id: str,
    scene_id: str,
    source: str,
    scene_service: SceneService,
) -> Scene:
    """
    Activate a scene via the same logic the API uses.

    SceneService.activate_scene:
      - loads the scene + actions
      - calls DeviceService.set_device_state for each action
      - logs a scene_activation event
    """
    scene = scene_service.activate_scene(
        yacht_id=yacht_id,
        source=source,
        scene_id=scene_id,
    )
    return scene
