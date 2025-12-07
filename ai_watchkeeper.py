# ai_watchkeeper.py

import os
import asyncio
import uuid
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, List

import httpx
from openai import OpenAI

# ----------------------
# CONFIG
# ----------------------

BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000")
YACHT_ID = os.getenv("YACHT_ID", "marex-21-001")

# How often to poll the backend
POLL_INTERVAL_SECONDS = 5

# Bilge pump protection (seconds)
BILGE_MAX_PUMP_SECONDS = 30   # ON time before enforced rest
BILGE_REST_SECONDS = 20       # Rest time before we allow AI to re-enable

client = OpenAI()  # uses OPENAI_API_KEY from environment

# ----------------------
# INTERNAL STATE
# ----------------------
# These are *only* in the AI process; no DB/schema changes.

bilge_pump_on_since: Optional[datetime] = None       # when override went True
bilge_forced_rest_until: Optional[datetime] = None   # until when AI won't re-arm
bilge_last_forced_by_ai: bool = False               # did AI last control override?

# Sensor latch: device_id -> datetime until which the sensor is treated as True
sensor_latches: Dict[str, datetime] = {}


def get_sensor_state_with_latch(device_id: str, device: Optional[dict], hold_seconds: int = 60) -> bool:
    """
    For tests and noisy signals, treat a sensor as TRUE for `hold_seconds`
    after the last time we saw it True.

    - If raw sensor is True now -> latch it for hold_seconds and return True.
    - If raw sensor is False but we're still within the latch window -> return True.
    - If latch expired and raw sensor is False -> return False.
    """
    global sensor_latches

    now = datetime.now(timezone.utc)
    raw_state = bool(device and device.get("state") is True)

    # Rising edge: sensor currently True
    if raw_state:
        sensor_latches[device_id] = now + timedelta(seconds=hold_seconds)
        return True

    # Check existing latch
    expiry = sensor_latches.get(device_id)
    if expiry and now < expiry:
        return True

    # Latch expired / never set
    if device_id in sensor_latches:
        sensor_latches.pop(device_id)

    return False


async def fetch_snapshot(http: httpx.AsyncClient):
    url = f"{BACKEND_BASE_URL}/yachts/{YACHT_ID}/ai/state_snapshot"
    resp = await http.get(url, timeout=5.0)
    resp.raise_for_status()
    return resp.json()


async def send_ai_commands(http: httpx.AsyncClient, payload: dict):
    """
    APPLY actions directly via /devices/.../state and /scenes/.../activate,
    instead of posting the whole payload to /ai/commands.
    """
    actions = payload.get("actions", []) or []
    applied = 0
    skipped = 0
    failed = 0
    errors: List[str] = []

    for action in actions:
        a_type = action.get("type")

        if a_type == "set_device_state":
            device_id = action.get("device_id")
            if not device_id:
                skipped += 1
                continue

            target_state = action.get("target_state")
            url = f"{BACKEND_BASE_URL}/yachts/{YACHT_ID}/devices/{device_id}/state"
            body = {
                "state": target_state,
                "source": "ai_watchkeeper",
            }
            try:
                resp = await http.post(url, json=body, timeout=5.0)
                resp.raise_for_status()
                applied += 1
            except Exception as e:
                failed += 1
                errors.append(f"{device_id}: {e}")

        elif a_type == "activate_scene":
            scene_id = action.get("scene_id") or action.get("device_id")
            if not scene_id:
                skipped += 1
                continue

            url = f"{BACKEND_BASE_URL}/yachts/{YACHT_ID}/scenes/{scene_id}/activate"
            body = {"source": "ai_watchkeeper"}
            try:
                resp = await http.post(url, json=body, timeout=5.0)
                resp.raise_for_status()
                applied += 1
            except Exception as e:
                failed += 1
                errors.append(f"scene {scene_id}: {e}")

        elif a_type == "no_op":
            skipped += 1

        else:
            # Unknown action type – ignore
            skipped += 1

    if failed:
        # Raise one combined error so loop_once logs it, but AFTER trying all actions
        raise RuntimeError(f"{failed} actions failed: {', '.join(errors)}")

    # Return a small summary (loop_once just prints it)
    return {
        "applied": applied,
        "skipped": skipped,
        "failed": failed,
    }


def infer_mode(snapshot: dict) -> str:
    """
    Heuristic 'mode' inference so we don't need DB/schema changes yet.

    Rules:
    - If nav_lights is True -> assume 'underway'
    - Else if anchor_light True and nav_lights False -> 'anchor'
    - Else -> 'in_port'
    """
    devices = snapshot.get("devices", [])

    def find(dev_id: str) -> Optional[dict]:
        return next((d for d in devices if d.get("id") == dev_id), None)

    anchor = find("anchor_light")
    nav = find("nav_lights")

    anchor_on = bool(anchor and anchor.get("state") is True)
    nav_on = bool(nav and nav.get("state") is True)

    if nav_on:
        return "underway"
    if anchor_on and not nav_on:
        return "anchor"
    return "in_port"


def get_occupancy(snapshot: dict) -> str:
    """
    Read occupancy from snapshot['occupancy'] if present,
    else fall back to 'unknown'.
    """
    return snapshot.get("occupancy", "unknown") or "unknown"


def build_prompt(snapshot: dict) -> str:
    """
    System prompt defining the model's high-level behaviour.

    The snapshot JSON we send to you will include:
    - 'mode' field inferred as: 'anchor', 'underway', or 'in_port'.
    - 'occupancy' field: 'onboard', 'unattended', or 'unknown'.
    """
    return (
        "You are an AI watchkeeper for a small yacht.\n"
        "- Input is JSON with devices, alarms, events, mode and occupancy.\n"
        "- 'mode' reflects vessel status: 'anchor', 'underway', or 'in_port'.\n"
        "- 'occupancy' reflects whether people are on board:\n"
        "    * 'onboard'    -> crew/guests present; be conservative, avoid micro-managing\n"
        "                      comfort lighting and non-critical devices unless safety is at risk.\n"
        "    * 'unattended' -> nobody aboard; you may take full control of safety-related devices\n"
        "                      and reasonable lighting to indicate status and conserve power.\n"
        "- You must obey COLREGs for navigation/anchor lights based on mode.\n"
        "  * mode='anchor': anchor light ON, navigation lights OFF.\n"
        "  * mode='underway': navigation lights ON, anchor light OFF.\n"
        "  * mode='in_port': be conservative; avoid turning on unnecessary bright deck lights at night.\n"
        "- Only use these action types: set_device_state, activate_scene, no_op.\n"
        "- Only ever touch devices and scenes that are clearly related to safety or lighting.\n"
        "- If no action is needed, return a single 'no_op' action.\n"
        "- Output MUST be a JSON object with an 'actions' array.\n"
        "- Each action should have: action_id, type, device_id or scene_id, target_state,\n"
        "  priority, constraints, reason.\n"
        "- Don't invent device IDs or scene IDs; only use what is in the snapshot.\n"
        "- Do NOT issue any actions that change the state of 'bilge_pump_auto_override'.\n"
        "  That device is controlled by deterministic safety rules outside of your control.\n"
        "- You may still suggest actions for lighting or other safety-related devices.\n"
    )


def filter_model_bilge_actions(payload: dict) -> None:
    """
    Strip any model-proposed actions touching bilge_pump_auto_override.
    Deterministic rules own that device completely.
    """
    actions = payload.get("actions", [])
    filtered = []
    for a in actions:
        if (
            a.get("type") == "set_device_state"
            and a.get("device_id") == "bilge_pump_auto_override"
        ):
            # Drop it
            continue
        filtered.append(a)
    payload["actions"] = filtered


def enforce_nav_light_rules(snapshot: dict, payload: dict) -> dict:
    """
    Hard COLREGs rules around anchor_light and nav_lights,
    on top of whatever the model suggests.

    - Uses inferred mode from current snapshot.
    - Only acts on lights where ai_control is truthy.
    - Avoids fighting manual control if ai_control is False/empty.
    """
    devices = snapshot.get("devices", [])
    actions = payload.get("actions", [])
    mode = infer_mode(snapshot)

    def find(dev_id: str) -> Optional[dict]:
        return next((d for d in devices if d.get("id") == dev_id), None)

    def is_on(dev: Optional[dict]) -> bool:
        return bool(dev and dev.get("state") is True)

    def ai_allowed(dev: Optional[dict]) -> bool:
        return bool(dev and dev.get("ai_control"))

    anchor = find("anchor_light")
    nav = find("nav_lights")

    anchor_state_now = is_on(anchor)
    nav_state_now = is_on(nav)

    # First pass: drop obviously illegal actions according to mode
    corrected_actions: List[dict] = []
    for a in actions:
        if a.get("type") == "set_device_state":
            dev_id = a.get("device_id")
            target = a.get("target_state")

            # Anchor mode rules
            if mode == "anchor":
                if dev_id == "nav_lights" and ai_allowed(nav) and target is True:
                    # Don't allow nav lights ON at anchor
                    continue
                if dev_id == "anchor_light" and ai_allowed(anchor) and target is False:
                    # Don't allow anchor light OFF at anchor
                    continue

            # Underway rules
            if mode == "underway":
                if dev_id == "anchor_light" and ai_allowed(anchor) and target is True:
                    # Don't allow anchor light ON underway
                    continue
                # For nav_lights, we allow True; False can be corrected by hard rule below.

        corrected_actions.append(a)

    actions = corrected_actions

    # Re-evaluate states (we could simulate actions, but for now we key off snapshot)
    anchor_on = anchor_state_now
    nav_on = nav_state_now

    # Now *enforce* mandatory states by appending corrective actions if needed.
    if mode == "anchor":
        # Anchor light must be ON
        if ai_allowed(anchor) and not anchor_on:
            actions.append(
                {
                    "action_id": f"rule-nav-anchor-{uuid.uuid4().hex[:6]}",
                    "type": "set_device_state",
                    "device_id": "anchor_light",
                    "scene_id": None,
                    "target_state": True,
                    "priority": "high",
                    "constraints": {},
                    "reason": "Vessel in anchor mode – ensuring anchor light is ON as per COLREGs.",
                }
            )

        # Nav lights must be OFF
        if ai_allowed(nav) and nav_on:
            actions.append(
                {
                    "action_id": f"rule-nav-anchor-{uuid.uuid4().hex[:6]}",
                    "type": "set_device_state",
                    "device_id": "nav_lights",
                    "scene_id": None,
                    "target_state": False,
                    "priority": "high",
                    "constraints": {},
                    "reason": "Vessel in anchor mode – turning navigation lights OFF as per COLREGs.",
                }
            )

    elif mode == "underway":
        # Nav lights must be ON
        if ai_allowed(nav) and not nav_on:
            actions.append(
                {
                    "action_id": f"rule-nav-underway-{uuid.uuid4().hex[:6]}",
                    "type": "set_device_state",
                    "device_id": "nav_lights",
                    "scene_id": None,
                    "target_state": True,
                    "priority": "high",
                    "constraints": {},
                    "reason": "Vessel underway – ensuring navigation lights are ON as per COLREGs.",
                }
            )

        # Anchor light must be OFF
        if ai_allowed(anchor) and anchor_on:
            actions.append(
                {
                    "action_id": f"rule-nav-underway-{uuid.uuid4().hex[:6]}",
                    "type": "set_device_state",
                    "device_id": "anchor_light",
                    "scene_id": None,
                    "target_state": False,
                    "priority": "high",
                    "constraints": {},
                    "reason": "Vessel underway – ensuring anchor light is OFF as per COLREGs.",
                }
            )

    # in_port: we don't force anything, just let the model decide (plus your manual control)

    payload["actions"] = actions
    return payload


def drop_idempotent_actions(snapshot: dict, payload: dict) -> dict:
    """
    Remove set_device_state actions that would not change anything
    (target_state == current state in snapshot).
    """
    devices = snapshot.get("devices", [])
    dev_map = {d.get("id"): d for d in devices if d.get("id")}

    filtered = []
    for a in payload.get("actions", []):
        # Only apply this optimisation to set_device_state
        if a.get("type") != "set_device_state":
            filtered.append(a)
            continue

        dev_id = a.get("device_id")
        target = a.get("target_state")

        if not dev_id:
            filtered.append(a)
            continue

        dev = dev_map.get(dev_id)
        if dev is None:
            # unknown device, keep it (backend can reject if invalid)
            filtered.append(a)
            continue

        current = dev.get("state")

        # If the target is the same as current, don't bother sending
        if current == target:
            continue

        filtered.append(a)

    payload["actions"] = filtered
    return payload


def build_human_explanation(snapshot: dict, command_payload: dict) -> str:
    """
    Build a short, human-readable explanation of what the AI did this cycle.
    This is local – no extra model calls.
    """
    devices = snapshot.get("devices", [])
    mode = infer_mode(snapshot)
    occupancy = get_occupancy(snapshot)

    def find(dev_id: str) -> Optional[dict]:
        return next((d for d in devices if d.get("id") == dev_id), None)

    bilge_high = find("bilge_float_high")
    bilge_override = find("bilge_pump_auto_override")
    anchor = find("anchor_light")
    nav = find("nav_lights")

    def on(dev: Optional[dict]) -> str:
        if dev is None:
            return "n/a"
        return "ON" if dev.get("state") is True else "OFF"

    lines: List[str] = []
    lines.append(f"Mode: {mode}.")
    lines.append(f"Occupancy: {occupancy}.")
    lines.append(
        f"Bilge high float: {on(bilge_high)}, bilge auto override: {on(bilge_override)}."
    )
    lines.append(
        f"Anchor light: {on(anchor)}, nav lights: {on(nav)}."
    )

    actions = command_payload.get("actions", [])
    if not actions:
        lines.append("No actions generated.")
        return " ".join(lines)

    # If it's just a no-op, keep it simple.
    if len(actions) == 1 and actions[0].get("type") == "no_op":
        lines.append("No intervention required – all conditions within normal limits.")
        return " ".join(lines)

    # Otherwise, summarise each action briefly.
    lines.append(f"Actions taken this cycle: {len(actions)}.")
    for a in actions:
        t = a.get("type")
        dev_id = a.get("device_id") or a.get("scene_id")
        tgt = a.get("target_state")
        reason = a.get("reason", "")
        if t == "set_device_state":
            lines.append(f"- Set '{dev_id}' to {tgt} ({reason})")
        elif t == "activate_scene":
            lines.append(f"- Activated scene '{dev_id}' ({reason})")
        elif t == "no_op":
            lines.append(f"- No-op: {reason}")
        else:
            lines.append(f"- {t} on '{dev_id}' ({reason})")

    return " ".join(lines)


async def send_ai_log(http: httpx.AsyncClient, snapshot: dict, command_payload: dict, explanation: str):
    """
    Send a human-readable log entry to the backend so the UI can display it.
    """
    url = f"{BACKEND_BASE_URL}/yachts/{YACHT_ID}/ai/logs"

    mode = infer_mode(snapshot)
    occupancy = get_occupancy(snapshot)

    payload = {
        "generated_at": command_payload.get("generated_at") or datetime.now(timezone.utc).isoformat(),
        "summary": explanation,
        "actions": command_payload.get("actions", []),
        "mode": f"{mode} (occupancy={occupancy})",
    }

    try:
        await http.post(url, json=payload, timeout=5.0)
    except Exception as e:
        # Don't ever break the watchkeeper if logging fails.
        print(f"[watchkeeper] Failed to send AI log: {e}")


def apply_hard_rules(snapshot: dict, payload: dict) -> dict:
    """
    Safety net rules that apply even if the model is dumb or returns no-op.
    - Bilge pump deterministic logic (with 60s latch + runtime limit + rest).
    - COLREGs hard rules for navigation/anchor lights.
    - Strips any model attempt to control the bilge override.
    """
    global bilge_pump_on_since, bilge_forced_rest_until, bilge_last_forced_by_ai

    # 0) Remove any model-produced actions on the bilge override
    filter_model_bilge_actions(payload)

    now = datetime.now(timezone.utc)
    devices = snapshot.get("devices", [])
    actions = payload.get("actions", [])

    # Find relevant devices
    bilge_high = next((d for d in devices if d.get("id") == "bilge_float_high"), None)
    bilge_override = next((d for d in devices if d.get("id") == "bilge_pump_auto_override"), None)

    # Use latched state for high bilge: stays True for 60s after last True
    bilge_high_state = get_sensor_state_with_latch("bilge_float_high", bilge_high, hold_seconds=60)

    override_state = bool(bilge_override and bilge_override.get("state") is True)
    override_ai_allowed = bool(bilge_override and bilge_override.get("ai_control"))

    # 1) Track when the pump has been ON (override True)
    if override_state:
        if bilge_pump_on_since is None:
            bilge_pump_on_since = now
    else:
        bilge_pump_on_since = None

    # 2) AUTO-ON RULE (safety)
    if (
        bilge_high_state
        and bilge_override
        and override_ai_allowed
        and not override_state
    ):
        in_rest_window = bilge_forced_rest_until is not None and now < bilge_forced_rest_until
        if not in_rest_window:
            actions.append(
                {
                    "action_id": f"rule-bilge-{uuid.uuid4().hex[:6]}",
                    "type": "set_device_state",
                    "device_id": "bilge_pump_auto_override",
                    "scene_id": None,
                    "target_state": True,
                    "priority": "critical",
                    "constraints": {
                        "only_if": {
                            "bilge_float_high": True
                        }
                    },
                    "reason": "Bilge high float is active and override is OFF – forcing pump ON for safety.",
                }
            )
            # We just took control
            bilge_last_forced_by_ai = True

    # 3) RUNTIME LIMIT RULE
    if (
        bilge_high_state
        and bilge_override
        and override_ai_allowed
        and override_state
        and bilge_pump_on_since is not None
    ):
        elapsed = (now - bilge_pump_on_since).total_seconds()
        if elapsed >= BILGE_MAX_PUMP_SECONDS:
            actions.append(
                {
                    "action_id": f"rule-bilge-rest-{uuid.uuid4().hex[:6]}",
                    "type": "set_device_state",
                    "device_id": "bilge_pump_auto_override",
                    "scene_id": None,
                    "target_state": False,
                    "priority": "critical",
                    "constraints": {},
                    "reason": (
                        f"Bilge pump has been ON for about {BILGE_MAX_PUMP_SECONDS} seconds "
                        "with high float still active – turning OFF briefly to protect the pump, "
                        f"and will allow restart after ~{BILGE_REST_SECONDS} seconds if high float persists."
                    ),
                }
            )
            bilge_forced_rest_until = now + timedelta(seconds=BILGE_REST_SECONDS)
            bilge_pump_on_since = None
            # This OFF is clearly AI-originated
            bilge_last_forced_by_ai = True

    # 4) HIGH FLOAT CLEARED RULE (AFTER AI-DRIVEN USE)
    if (
        not bilge_high_state
        and bilge_override
        and override_ai_allowed
        and override_state
        and bilge_last_forced_by_ai
    ):
        actions.append(
            {
                "action_id": f"rule-bilge-clear-{uuid.uuid4().hex[:6]}",
                "type": "set_device_state",
                "device_id": "bilge_pump_auto_override",
                "scene_id": None,
                "target_state": False,
                "priority": "critical",
                "constraints": {},
                "reason": "Bilge high float cleared after AI-driven pump use – turning bilge pump override OFF.",
            }
        )
        # We've cleaned up after ourselves
        bilge_last_forced_by_ai = False
        bilge_pump_on_since = None
        bilge_forced_rest_until = None

    payload["actions"] = actions

    # 5) COLREGs navigation/anchor light enforcement
    payload = enforce_nav_light_rules(snapshot, payload)

    # 6) Drop actions that wouldn't actually change device state
    payload = drop_idempotent_actions(snapshot, payload)

    return payload


async def call_model(snapshot: dict) -> dict:
    now = datetime.now(timezone.utc)
    request_id = f"ai-{now.isoformat()}-{uuid.uuid4().hex[:8]}"

    system_prompt = build_prompt(snapshot)

    # Add inferred mode and occupancy into the JSON that the model sees
    mode = infer_mode(snapshot)
    occupancy = get_occupancy(snapshot)

    snapshot_for_model = dict(snapshot)
    snapshot_for_model["mode"] = mode
    snapshot_for_model["occupancy"] = occupancy

    completion = client.chat.completions.create(
        model="gpt-5-nano",  # default temperature=1
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": (
                    "Here is the current yacht state snapshot as JSON, including inferred 'mode' "
                    f"and 'occupancy' (current='{occupancy}'). Decide if you want to take any actions.\n\n"
                    + json.dumps(snapshot_for_model)
                ),
            },
        ],
    )

    raw_json = completion.choices[0].message.content
    payload = json.loads(raw_json)

    # Fill in mandatory metadata
    payload.setdefault("yacht_id", YACHT_ID)
    payload.setdefault("request_id", request_id)
    payload.setdefault("requested_by", "ai_watchkeeper")
    payload.setdefault("generated_at", now.isoformat())
    payload.setdefault("actions", [])

    # 🔒 Apply hard safety rules on top of whatever the model said
    payload = apply_hard_rules(snapshot, payload)

    # If after hard rules there are still no actions, inject a no-op
    if not payload["actions"]:
        payload["actions"] = [
            {
                "action_id": "noop-1",
                "type": "no_op",
                "device_id": None,
                "scene_id": None,
                "target_state": None,
                "priority": "info",
                "constraints": {},
                "reason": "No action required.",
            }
        ]

    return payload


async def loop_once(http: httpx.AsyncClient):
    try:
        snapshot = await fetch_snapshot(http)
    except Exception as e:
        print(f"[watchkeeper] Failed to fetch snapshot: {e}")
        return

    try:
        command_payload = await call_model(snapshot)
    except Exception as e:
        print(f"[watchkeeper] Model call failed: {e}")
        return

    # Build human-readable explanation
    explanation = build_human_explanation(snapshot, command_payload)

    # Send AI log to backend (non-critical)
    await send_ai_log(http, snapshot, command_payload, explanation)

    # DEBUG: see exactly what we are sending to the backend
    print("[watchkeeper] command_payload:")
    print(json.dumps(command_payload, indent=2))

    try:
        result = await send_ai_commands(http, command_payload)
        print(f"[watchkeeper] Commands processed: {result}")
    except Exception as e:
        print(f"[watchkeeper] Failed to apply commands: {e}")


async def main():
    async with httpx.AsyncClient() as http:
        while True:
            await loop_once(http)
            await asyncio.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
