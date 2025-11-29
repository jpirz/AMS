# ai_watchkeeper.py

import os
import asyncio
import uuid
import json
from datetime import datetime, timezone, timedelta

import httpx
from openai import OpenAI

BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000")
YACHT_ID = os.getenv("YACHT_ID", "marex-21-001")
POLL_INTERVAL_SECONDS = 5

# === Bilge cycling safety config ===
BILGE_HIGH_SENSOR_ID = "bilge_float_high"
BILGE_PUMP_DEVICE_ID = "bilge_pump_auto_override"  # device the AI is allowed to manage

BILGE_MAX_RUN_SECONDS = 30   # max continuous ON time
BILGE_REST_SECONDS = 20      # OFF time before restarting if high float still true

# Internal state for this watchkeeper process
_bilge_pump_last_on_time = None  # type: datetime | None
_bilge_forced_off_until = None   # type: datetime | None

client = OpenAI()  # uses OPENAI_API_KEY


async def fetch_snapshot(http: httpx.AsyncClient):
    url = f"{BACKEND_BASE_URL}/yachts/{YACHT_ID}/ai/state_snapshot"
    resp = await http.get(url, timeout=5.0)
    resp.raise_for_status()
    return resp.json()


async def send_ai_commands(http: httpx.AsyncClient, payload: dict):
    url = f"{BACKEND_BASE_URL}/yachts/{YACHT_ID}/ai/commands"
    resp = await http.post(url, json=payload, timeout=5.0)
    resp.raise_for_status()
    return resp.json()


def build_prompt(snapshot: dict) -> str:
    """
    System prompt is where you define behaviour.
    """
    return (
        "You are an AI watchkeeper for a small yacht.\n"
        "- Input is JSON with devices, alarms, events, mode.\n"
        "- Your job: decide if any actions are needed.\n"
        "- Only use these action types: set_device_state, activate_scene, no_op.\n"
        "- Only ever touch devices and scenes that are clearly related to safety or lighting.\n"
        "- If no action is needed, return a single 'no_op' action.\n"
        "- Output MUST be a JSON object with an 'actions' array.\n"
        "- Each action should have: action_id, type, device_id or scene_id, target_state, "
        "priority, constraints, reason.\n"
        "- Don't invent device IDs or scene IDs; only use what is in the snapshot.\n"
        "- When bilge high float is TRUE and bilge_pump_auto_override is OFF, you SHOULD "
        "request bilge_pump_auto_override ON, with a constraint that bilge_float_high is still TRUE.\n"
    )


def apply_hard_rules(snapshot: dict, payload: dict) -> dict:
    """
    Safety net rules that apply even if the model is dumb or returns no-op.

    This includes:
      - Taking ownership of the bilge override device
      - Ensuring:
          * Pump is OFF when high float is OFF
          * Pump is limited to BILGE_MAX_RUN_SECONDS at a time
          * If high float stays ON, pump is restarted after BILGE_REST_SECONDS
    """
    global _bilge_pump_last_on_time, _bilge_forced_off_until

    devices = snapshot.get("devices", [])
    actions = payload.get("actions", [])

    # Strip out any model-proposed actions that touch the bilge override.
    # Safety logic below is the single authority for this device.
    cleaned_actions = []
    for a in actions:
        if (
            a.get("type") == "set_device_state"
            and a.get("device_id") == BILGE_PUMP_DEVICE_ID
        ):
            continue
        cleaned_actions.append(a)
    actions = cleaned_actions

    bilge_high = next((d for d in devices if d.get("id") == BILGE_HIGH_SENSOR_ID), None)
    bilge_override = next((d for d in devices if d.get("id") == BILGE_PUMP_DEVICE_ID), None)

    # If we don't see these devices, do nothing.
    if bilge_high is None or bilge_override is None:
        payload["actions"] = actions
        return payload

    # Only manage this device if AI control is allowed.
    if not bilge_override.get("ai_control"):
        payload["actions"] = actions
        return payload

    now = datetime.now(timezone.utc)
    high = bilge_high.get("state") is True
    pump_on = bilge_override.get("state") is True

    # Track pump ON duration
    if pump_on:
        if _bilge_pump_last_on_time is None:
            _bilge_pump_last_on_time = now
    else:
        _bilge_pump_last_on_time = None

    def add_bilge_action(on: bool, reason: str, priority: str = "critical"):
        actions.append(
            {
                "action_id": f"rule-bilge-{uuid.uuid4().hex[:6]}",
                "type": "set_device_state",
                "device_id": BILGE_PUMP_DEVICE_ID,
                "scene_id": None,
                "target_state": on,
                "priority": priority,
                # When turning ON, require that the high float is still active.
                "constraints": {
                    "only_if": {
                        BILGE_HIGH_SENSOR_ID: True
                    }
                } if on else {},
                "reason": reason,
            }
        )

    # --- Case 1: high float is OFF -> pump must be OFF, clear timers ---
    if not high:
        if pump_on:
            add_bilge_action(
                False,
                "Bilge high float cleared – turning bilge pump override OFF."
            )
        _bilge_pump_last_on_time = None
        _bilge_forced_off_until = None
        payload["actions"] = actions
        return payload

    # From here: high float is TRUE

    # --- Case 2: pump is ON – enforce max runtime ---
    if pump_on and _bilge_pump_last_on_time is not None:
        run_seconds = (now - _bilge_pump_last_on_time).total_seconds()
        if run_seconds >= BILGE_MAX_RUN_SECONDS:
            _bilge_forced_off_until = now + timedelta(seconds=BILGE_REST_SECONDS)
            _bilge_pump_last_on_time = None
            add_bilge_action(
                False,
                (
                    f"Bilge pump has been ON for {int(run_seconds)}s with high float still active – "
                    f"turning OFF for a {BILGE_REST_SECONDS}s rest period."
                ),
            )
            payload["actions"] = actions
            return payload

    # --- Case 3: pump is OFF while high float is TRUE ---
    if not pump_on:
        # If we're in a forced rest window, do nothing until it expires.
        if _bilge_forced_off_until is not None and now < _bilge_forced_off_until:
            payload["actions"] = actions
            return payload

        # Either there was no rest window or it expired – turn pump ON again.
        add_bilge_action(
            True,
            "Bilge high float is active and pump is OFF – turning bilge pump override ON."
        )
        _bilge_pump_last_on_time = now
        _bilge_forced_off_until = None
        payload["actions"] = actions
        return payload

    # If we get here: high float TRUE, pump ON, under max runtime -> nothing extra to do.
    payload["actions"] = actions
    return payload


async def call_model(snapshot: dict) -> dict:
    now = datetime.now(timezone.utc)
    request_id = f"ai-{now.isoformat()}-{uuid.uuid4().hex[:8]}"

    system_prompt = build_prompt(snapshot)

    completion = client.chat.completions.create(
        model="gpt-4o-mini",  # keep as-is; can upgrade later
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": (
                    "Here is the current yacht state snapshot as JSON. "
                    "Decide if you want to take any actions.\n\n"
                    + json.dumps(snapshot)
                ),
            },
        ],
        temperature=0.1,
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

    # 🔎 DEBUG: see exactly what we are sending to the backend
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
