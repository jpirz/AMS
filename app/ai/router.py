# app/ai/router.py

from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from typing import List

from app.ai.schemas import (
    AIStateSnapshot,
    AICommandRequest,
    AICommandResponse,
    AICommandResultItem,
    AIExecutedAction,
)
from app.ai.policy import get_device_level, get_scene_level

# These you already have somewhere; import from your existing modules
from app.devices import get_devices_for_yacht, set_device_state_internal
from app.scenes import get_active_scenes_for_yacht, activate_scene_internal
from app.events import get_recent_events_for_yacht, get_derived_alarms_for_yacht
from app.mode import get_current_mode_for_yacht, get_time_of_day_for_yacht


router = APIRouter(prefix="/yachts/{yacht_id}/ai", tags=["ai"])


@router.get("/state_snapshot", response_model=AIStateSnapshot)
async def get_state_snapshot(yacht_id: str) -> AIStateSnapshot:
    """
    Read-only: used by the external AI process.
    No state changes here.
    """
    devices = await get_devices_for_yacht(yacht_id)
    events = await get_recent_events_for_yacht(yacht_id, limit=200)
    alarms = await get_derived_alarms_for_yacht(yacht_id)
    mode = await get_current_mode_for_yacht(yacht_id)
    active_scenes = await get_active_scenes_for_yacht(yacht_id)
    time_of_day = await get_time_of_day_for_yacht(yacht_id)

    now = datetime.now(timezone.utc)

    return AIStateSnapshot(
        yacht_id=yacht_id,
        snapshot_timestamp=now,
        mode=mode,
        active_scenes=active_scenes,
        devices=devices,          # assuming your helpers already build AIDevice objects
        derived_alarms=alarms,    # same for AIAlarm
        recent_events=events,     # same for AIEvent
        env={
            "now_local": now,     # you can convert to local TZ if you want
            "time_of_day": time_of_day,
            "location_hint": None
        }
    )


@router.post("/commands", response_model=AICommandResponse)
async def apply_ai_commands(
    yacht_id: str,
    cmd: AICommandRequest,
) -> AICommandResponse:
    """
    Only place where AI commands can actually affect hardware.
    Applies whitelist + safety rules + rate limiting.
    """
    if cmd.yacht_id != yacht_id:
        raise HTTPException(status_code=400, detail="yacht_id mismatch")

    now = datetime.now(timezone.utc)
    results: List[AICommandResultItem] = []

    # Optional: re-fetch snapshot here to evaluate conditions safely
    devices = {d.id: d for d in await get_devices_for_yacht(yacht_id)}
    mode = await get_current_mode_for_yacht(yacht_id)

    for action in cmd.actions:
        # Default result, possibly overridden below
        status = "rejected"
        reason = "Not processed"
        executed_as = None

        if action.type == "no_op":
            results.append(
                AICommandResultItem(
                    action_id=action.action_id,
                    status="executed",
                    reason="No-op acknowledged",
                    executed_as=AIExecutedAction(
                        type="no_op",
                        device_id=None,
                        scene_id=None,
                        target_state=None,
                        source="ai_watchkeeper",
                    ),
                )
            )
            continue

        # Device-level controls
        if action.type == "set_device_state" and action.device_id:
            device_id = action.device_id
            level = get_device_level(device_id)
            if level == 0:
                status = "rejected"
                reason = f"Device '{device_id}' is not AI-controllable (level 0)."
            elif level == 1:
                status = "deferred"
                reason = f"Device '{device_id}' is suggestion-only (level 1)."
                # No real execution, you could log a suggestion here
            else:
                # level >= 2 → allowed if passes safety rules
                dev = devices.get(device_id)
                if dev is None:
                    status = "rejected"
                    reason = f"Device '{device_id}' not found."
                else:
                    # Evaluate 'only_if' constraints
                    if action.constraints and action.constraints.only_if:
                        for dep_id, expected_val in action.constraints.only_if.device_state_equals.items():
                            dep_dev = devices.get(dep_id)
                            if dep_dev is None or dep_dev.state != expected_val:
                                status = "rejected"
                                reason = f"Condition failed: {dep_id} != {expected_val!r}."
                                break
                        else:
                            # all conditions passed
                            pass

                        if status == "rejected":
                            results.append(
                                AICommandResultItem(
                                    action_id=action.action_id,
                                    status=status,
                                    reason=reason,
                                    executed_as=None,
                                )
                            )
                            continue

                    # TODO: add bilge-specific safety rules, rate limits, etc.
                    # For now, we trust that policy allows this.
                    new_state = action.target_state
                    await set_device_state_internal(
                        yacht_id=yacht_id,
                        device_id=device_id,
                        state=new_state,
                        source="ai_watchkeeper",
                    )
                    status = "executed"
                    reason = "Executed by AI within policy."
                    executed_as = AIExecutedAction(
                        type="set_device_state",
                        device_id=device_id,
                        scene_id=None,
                        target_state=new_state,
                        source="ai_watchkeeper",
                    )

        # Scene-level controls
        elif action.type in ("activate_scene", "deactivate_scene") and action.scene_id:
            scene_id = action.scene_id
            level = get_scene_level(scene_id)
            if level == 0:
                status = "rejected"
                reason = f"Scene '{scene_id}' is not AI-controllable (level 0)."
            elif level == 1:
                status = "deferred"
                reason = f"Scene '{scene_id}' is suggestion-only (level 1)."
            else:
                # level >= 2
                # Example safety: don't auto-switch from underway → at_anchor
                if mode == "underway" and scene_id == "at_anchor":
                    status = "rejected"
                    reason = "Refusing to switch to at_anchor while underway."
                else:
                    await activate_scene_internal(
                        yacht_id=yacht_id,
                        scene_id=scene_id,
                        source="ai_watchkeeper",
                    )
                    status = "executed"
                    reason = "Scene activated by AI within policy."
                    executed_as = AIExecutedAction(
                        type="activate_scene",
                        device_id=None,
                        scene_id=scene_id,
                        target_state=None,
                        source="ai_watchkeeper",
                    )

        results.append(
            AICommandResultItem(
                action_id=action.action_id,
                status=status,
                reason=reason,
                executed_as=executed_as,
            )
        )

    return AICommandResponse(
        request_id=cmd.request_id,
        yacht_id=yacht_id,
        processed_at=now,
        results=results,
    )
