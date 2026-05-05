from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from openai import OpenAI
from pydantic import BaseModel, Field

from app.ai.schemas import (
    AICommandAction,
    AICommandRequest,
    AICommandResponse,
    AICommandResultItem,
    AIExecutedAction,
)
from app.auth import require_control_auth
from app.models import AiControlLevel, Device, DeviceType
from app.routers.yachts import yacht_meta
from app.services.core import (
    ai_state,
    ai_insights,
    alarm_service,
    device_service,
    event_logger,
    safety_service,
    scene_service,
    simulator_service,
    vessel_state,
)

router = APIRouter(prefix="/yachts/{yacht_id}/ai", tags=["ai"])

client = OpenAI()


class AIWatchLogIn(BaseModel):
    generated_at: datetime
    summary: str
    actions: List[dict] = Field(default_factory=list)
    mode: Optional[str] = None


class AIWatchLogOut(AIWatchLogIn):
    id: str


class AIOccupancyUpdate(BaseModel):
    occupancy: str = Field(..., pattern="^(onboard|unattended)$")


class AIChatRequest(BaseModel):
    message: str = Field(..., min_length=1)


class AIChatResponse(BaseModel):
    reply: str


class SuggestionApproveRequest(BaseModel):
    source: str = "user_ui"


class NaturalLanguageCommandRequest(BaseModel):
    message: str = Field(..., min_length=1)
    source: str = "web_ui"
    execute: bool = True


@router.get("/state_snapshot")
async def state_snapshot(yacht_id: str) -> Dict[str, Any]:
    devices = device_service.list_devices(yacht_id)
    scenes = scene_service.list_scenes(yacht_id)
    events = event_logger.list_events(yacht_id, limit=50)
    occupancy = ai_state.get_occupancy(yacht_id)
    alarms = alarm_service.active_alarms(yacht_id)

    return {
        "yacht": await yacht_meta(yacht_id),
        "devices": [d.model_dump(mode="json") for d in devices],
        "scenes": [s.model_dump(mode="json") for s in scenes],
        "events": [e.model_dump(mode="json") for e in events],
        "derived_alarms": alarms,
        "occupancy": occupancy,
        "mode": vessel_state.get_mode(yacht_id),
    }


@router.post("/commands", response_model=AICommandResponse, dependencies=[Depends(require_control_auth)])
async def apply_ai_commands(yacht_id: str, cmd: AICommandRequest) -> AICommandResponse:
    if cmd.yacht_id != yacht_id:
        raise HTTPException(status_code=400, detail="yacht_id mismatch")

    now = datetime.now(timezone.utc)
    devices = {d.id: d for d in device_service.list_devices(yacht_id)}
    mode = vessel_state.get_mode(yacht_id)
    results: List[AICommandResultItem] = []

    for action in cmd.actions:
        result = _execute_action(yacht_id, action, devices, mode)
        results.append(result)

    event_logger.log(
        yacht_id=yacht_id,
        source="ai_watchkeeper",
        type="ai_command",
        details={
            "request_id": cmd.request_id,
            "results": [r.model_dump(mode="json") for r in results],
        },
    )
    safety_service.enforce(yacht_id, source="ai_command_boundary")

    return AICommandResponse(
        request_id=cmd.request_id,
        yacht_id=yacht_id,
        processed_at=now,
        results=results,
    )


@router.post("/logs", response_model=AIWatchLogOut)
async def add_ai_log(yacht_id: str, log: AIWatchLogIn):
    return ai_state.add_log(
        yacht_id=yacht_id,
        generated_at=log.generated_at,
        summary=log.summary,
        actions=log.actions,
        mode=log.mode,
    )


@router.get("/logs", response_model=List[AIWatchLogOut])
async def list_ai_logs(yacht_id: str, limit: int = Query(50, ge=1, le=200)):
    return ai_state.list_logs(yacht_id, limit=limit)


@router.get("/occupancy")
async def get_occupancy(yacht_id: str):
    return {"yacht_id": yacht_id, "occupancy": ai_state.get_occupancy(yacht_id)}


@router.post("/occupancy")
async def set_occupancy(yacht_id: str, body: AIOccupancyUpdate):
    return ai_state.set_occupancy(yacht_id, body.occupancy)


@router.post("/chat", response_model=AIChatResponse)
async def ai_chat(yacht_id: str, body: AIChatRequest):
    user_message = body.message.strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="Empty message")

    devices = device_service.list_devices(yacht_id)[:20]
    events = event_logger.list_events(yacht_id, limit=10)
    occupancy = ai_state.get_occupancy(yacht_id)

    context_blob = {
        "yacht_id": yacht_id,
        "occupancy": occupancy,
        "devices": [
            {
                "id": d.id,
                "name": d.name,
                "zone": d.zone,
                "type": d.type.value,
                "state": d.state,
            }
            for d in devices
        ],
        "recent_events": [e.model_dump(mode="json") for e in events],
    }

    completion = client.chat.completions.create(
        model=os.getenv("AI_CHAT_MODEL", "gpt-5-nano"),
        messages=[
            {
                "role": "system",
                "content": (
                    "You are the AI watchkeeper for a small yacht. "
                    "Be concise, practical, and safety-focused. "
                    "Use current device states, occupancy, and recent events. "
                    "If you do not know something, say so."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Current yacht state (JSON):\n"
                    + json.dumps(context_blob, separators=(",", ":"), default=str)
                    + "\n\nUser question:\n"
                    + user_message
                ),
            },
        ],
    )

    reply = completion.choices[0].message.content.strip()
    event_logger.log(
        yacht_id=yacht_id,
        source="ai_chat",
        type="ai_chat",
        details={"message": user_message, "reply": reply},
    )
    return AIChatResponse(reply=reply)


@router.get("/status")
async def ai_status(yacht_id: str):
    return ai_insights.status_summary(yacht_id)


@router.get("/safety-explanations")
async def safety_explanations(yacht_id: str, limit: int = Query(20, ge=1, le=100)):
    return {
        "yacht_id": yacht_id,
        "explanations": ai_insights.safety_explanations(yacht_id, limit=limit),
    }


@router.get("/incidents")
async def incident_reports(yacht_id: str, limit: int = Query(20, ge=1, le=100)):
    return {
        "yacht_id": yacht_id,
        "incidents": ai_insights.incident_reports(yacht_id, limit=limit),
    }


@router.get("/maintenance")
async def maintenance_intelligence(yacht_id: str):
    return ai_insights.maintenance_intelligence(yacht_id)


@router.post("/nl-command", dependencies=[Depends(require_control_auth)])
async def natural_language_command(yacht_id: str, body: NaturalLanguageCommandRequest):
    return _handle_natural_language_command(yacht_id, body)


@router.get("/suggestions")
async def list_suggestions(yacht_id: str):
    return {
        "yacht_id": yacht_id,
        "suggestions": ai_insights.build_suggestions(yacht_id),
    }


@router.post("/suggestions/{suggestion_id}/approve", dependencies=[Depends(require_control_auth)])
async def approve_suggestion(
    yacht_id: str,
    suggestion_id: str,
    body: SuggestionApproveRequest | None = None,
):
    devices = {d.id: d for d in device_service.list_devices(yacht_id)}
    suggestions = {
        s["id"]: s
        for s in ai_insights.build_suggestions(yacht_id, devices=list(devices.values()))
    }
    suggestion = suggestions.get(suggestion_id)
    if suggestion is None:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    if not suggestion.get("action"):
        raise HTTPException(status_code=400, detail="Suggestion has no executable action")

    source = body.source if body else "user_ui"
    action = AICommandAction.model_validate(suggestion["action"])
    processed_at = datetime.now(timezone.utc)
    result_item = _execute_approved_action(yacht_id, action, devices, source=source)
    safety_service.enforce(yacht_id)
    result = AICommandResponse(
        request_id=f"approved-{suggestion_id}-{int(processed_at.timestamp())}",
        yacht_id=yacht_id,
        processed_at=processed_at,
        results=[result_item],
    )
    event_logger.log(
        yacht_id=yacht_id,
        source=source,
        type="ai_suggestion_approved",
        details={"suggestion_id": suggestion_id, "result": result.model_dump(mode="json")},
    )
    return result


def _handle_natural_language_command(
    yacht_id: str,
    body: NaturalLanguageCommandRequest,
) -> Dict[str, Any]:
    message = body.message.strip()
    text = _normalize_text(message)
    source = body.source or "web_ui"
    devices = {d.id: d for d in device_service.list_devices(yacht_id)}

    if _is_status_question(text):
        summary = ai_insights.status_summary(yacht_id)
        return {
            "status": "answered",
            "intent": "status_query",
            "reply": _status_reply(summary),
            "execute": False,
            "translated_commands": [],
            "summary": summary,
        }

    if "acknowledge" in text and "alarm" in text or text.startswith("ack alarm"):
        command = {"type": "acknowledge_alarms"}
        if not body.execute:
            return _preview_response("acknowledge_alarms", [command], "Ready to acknowledge active alarms.")
        result = alarm_service.acknowledge_active(yacht_id, source=source)
        event_logger.log(
            yacht_id=yacht_id,
            source=source,
            type="natural_language_command",
            details={"message": message, "commands": [command], "result": result},
        )
        return {
            "status": "executed",
            "intent": "acknowledge_alarms",
            "reply": f"Acknowledged {result['acknowledged']} active alarm(s).",
            "translated_commands": [command],
            "result": result,
        }

    if "clear" in text and "alarm" in text:
        command = {"type": "run_simulator_scenario", "scenario": "normal"}
        if not body.execute:
            return _preview_response("clear_test_alarms", [command], "Ready to reset test alarm sensors to normal.")
        result = simulator_service.run_scenario(yacht_id, "normal")
        event_logger.log(
            yacht_id=yacht_id,
            source=source,
            type="natural_language_command",
            details={"message": message, "commands": [command], "result": result},
        )
        return {
            "status": "executed",
            "intent": "clear_test_alarms",
            "reply": "Reset test alarm sensors to normal.",
            "translated_commands": [command],
            "result": result,
        }

    scene_match = _match_scene_or_mode(text)
    if scene_match:
        commands = []
        if scene_match.get("mode"):
            commands.append({"type": "set_vessel_mode", "mode": scene_match["mode"]})
        if scene_match.get("scene_id"):
            commands.append({"type": "activate_scene", "scene_id": scene_match["scene_id"]})

        if not body.execute:
            return _preview_response(scene_match["intent"], commands, scene_match["preview"])

        results: Dict[str, Any] = {}
        if scene_match.get("mode"):
            results["mode"] = vessel_state.set_mode(yacht_id, scene_match["mode"], source=source)
        if scene_match.get("scene_id"):
            action = AICommandAction(
                action_id=f"nl-scene-{scene_match['scene_id']}",
                type="activate_scene",
                scene_id=scene_match["scene_id"],
                priority="high",
                reason=f"Operator natural-language command: {message}",
            )
            results["scene"] = _execute_approved_action(yacht_id, action, devices, source=source).model_dump(mode="json")

        results["safety"] = safety_service.enforce(yacht_id, source="natural_language_command")
        alarm_service.sync_all(yacht_id)
        event_logger.log(
            yacht_id=yacht_id,
            source=source,
            type="natural_language_command",
            details={"message": message, "commands": commands, "result": results},
        )
        return {
            "status": "executed",
            "intent": scene_match["intent"],
            "reply": scene_match["reply"],
            "translated_commands": commands,
            "result": results,
        }

    device_match = _match_device_command(text, devices)
    if device_match:
        command = {
            "type": "set_device_state",
            "device_id": device_match["device"].id,
            "target_state": device_match["target_state"],
        }
        if device_match["device"].type == DeviceType.SENSOR:
            return {
                "status": "rejected",
                "intent": "set_device_state",
                "reply": f"{device_match['device'].name} is a sensor and cannot be controlled.",
                "translated_commands": [command],
            }
        if not body.execute:
            target = "ON" if device_match["target_state"] else "OFF"
            return _preview_response(
                "set_device_state",
                [command],
                f"Ready to set {device_match['device'].name} {target}.",
            )

        action = AICommandAction(
            action_id=f"nl-device-{device_match['device'].id}",
            type="set_device_state",
            device_id=device_match["device"].id,
            target_state=device_match["target_state"],
            priority="normal",
            reason=f"Operator natural-language command: {message}",
        )
        result_item = _execute_approved_action(yacht_id, action, devices, source=source)
        safety = safety_service.enforce(yacht_id, source="natural_language_command")
        event_logger.log(
            yacht_id=yacht_id,
            source=source,
            type="natural_language_command",
            details={
                "message": message,
                "commands": [command],
                "result": result_item.model_dump(mode="json"),
                "safety": safety,
            },
        )
        target = "ON" if device_match["target_state"] else "OFF"
        return {
            "status": result_item.status,
            "intent": "set_device_state",
            "reply": f"{device_match['device'].name} {target}: {result_item.reason}",
            "translated_commands": [command],
            "result": result_item.model_dump(mode="json"),
            "safety": safety,
        }

    return {
        "status": "rejected",
        "intent": "unknown",
        "reply": "I could not translate that into a safe typed command.",
        "translated_commands": [],
        "suggested_next_step": "Try 'turn on cabin fan', 'activate anchor mode', or 'acknowledge alarms'.",
    }


def _preview_response(intent: str, commands: List[Dict[str, Any]], reply: str) -> Dict[str, Any]:
    return {
        "status": "preview",
        "intent": intent,
        "reply": reply,
        "execute": False,
        "translated_commands": commands,
    }


def _normalize_text(value: str) -> str:
    return " ".join(
        value.lower()
        .replace("_", " ")
        .replace("-", " ")
        .replace("/", " ")
        .replace("?", " ?")
        .split()
    )


def _is_status_question(text: str) -> bool:
    question_terms = ["status", "health", "what is wrong", "what's wrong", "anything wrong", "battery ok", "battery okay"]
    if any(term in text for term in question_terms):
        return True
    return text.endswith("?") and not any(word in text for word in ["turn", "switch", "enable", "disable", "activate", "start", "stop"])


def _status_reply(summary: Dict[str, Any]) -> str:
    headline = summary["headline"]
    mode = summary["mode"].replace("_", " ")
    if summary["risk_items"]:
        top = summary["risk_items"][0]
        return f"{headline} Mode is {mode}. Top issue: {top['title']} - {top['reason']}"
    if summary["maintenance_alerts"]:
        top = summary["maintenance_alerts"][0]
        return f"{headline} Mode is {mode}. Maintenance: {top['title']} - {top['reason']}"
    return f"{headline} Mode is {mode}."


def _match_scene_or_mode(text: str) -> Dict[str, Any] | None:
    mentions_mode = "mode" in text or "scene" in text
    has_scene_command = "activate" in text or "set mode" in text or "set vessel" in text
    if not has_scene_command and not mentions_mode:
        return None

    if "anchor" in text and (mentions_mode or "at anchor" in text or "activate anchor" in text):
        return {
            "intent": "activate_anchor_mode",
            "mode": "at_anchor",
            "scene_id": "at_anchor",
            "preview": "Ready to set vessel mode to at anchor and activate the at-anchor scene.",
            "reply": "Set vessel mode to at anchor and activated the at-anchor scene.",
        }
    if "underway" in text or ("running" in text and mentions_mode):
        return {
            "intent": "activate_underway_mode",
            "mode": "underway",
            "scene_id": "underway",
            "preview": "Ready to set vessel mode to underway and activate the underway scene.",
            "reply": "Set vessel mode to underway and activated the underway scene.",
        }
    if "harbour" in text or "harbor" in text or "in port" in text or "port mode" in text:
        return {
            "intent": "activate_harbour_mode",
            "mode": "in_port",
            "scene_id": "harbour_mode",
            "preview": "Ready to set vessel mode to in port and activate harbour mode.",
            "reply": "Set vessel mode to in port and activated harbour mode.",
        }
    if "night" in text and (mentions_mode or "activate night" in text):
        return {
            "intent": "activate_night_mode",
            "scene_id": "night_mode",
            "preview": "Ready to activate night mode.",
            "reply": "Activated night mode.",
        }
    return None


def _match_device_command(text: str, devices: Dict[str, Device]) -> Dict[str, Any] | None:
    off_phrases = ["turn off", "switch off", "shut off", "disable", "stop"]
    on_phrases = ["turn on", "switch on", "enable", "start"]

    target_state: bool | None = None
    if any(phrase in text for phrase in off_phrases):
        target_state = False
    elif any(phrase in text for phrase in on_phrases):
        target_state = True
    if target_state is None:
        return None

    best: tuple[int, Device] | None = None
    for device in devices.values():
        aliases = {
            _normalize_text(device.id),
            _normalize_text(device.name),
            _normalize_text(device.name.replace("/", " ")),
        }
        for alias in aliases:
            if alias and alias in text:
                score = len(alias)
                if best is None or score > best[0]:
                    best = (score, device)

    if best is None:
        return None
    return {"device": best[1], "target_state": target_state}


def _execute_approved_action(
    yacht_id: str,
    action: AICommandAction,
    devices: Dict[str, Device],
    source: str,
) -> AICommandResultItem:
    if action.type == "set_device_state":
        if not action.device_id:
            return _result(action.action_id, "rejected", "Missing device_id.")

        device = devices.get(action.device_id)
        if device is None:
            return _result(action.action_id, "rejected", f"Device '{action.device_id}' not found.")
        if device.type == DeviceType.SENSOR:
            return _result(action.action_id, "rejected", "Sensors cannot be controlled.")
        if device.control_authority == "locked_out":
            return _result(action.action_id, "rejected", "Device is locked out.")

        try:
            updated = device_service.set_device_state(
                yacht_id=yacht_id,
                source=source,
                device_id=action.device_id,
                state=action.target_state,
            )
            alarm_service.sync_device(yacht_id, action.device_id, device=updated)
        except (KeyError, ValueError) as exc:
            return _result(action.action_id, "rejected", str(exc))

        return AICommandResultItem(
            action_id=action.action_id,
            status="executed",
            reason="Approved and executed by operator.",
            executed_as=AIExecutedAction(
                type="set_device_state",
                device_id=action.device_id,
                target_state=action.target_state,
                source=source,
            ),
        )

    if action.type == "activate_scene":
        if not action.scene_id:
            return _result(action.action_id, "rejected", "Missing scene_id.")
        try:
            scene_service.activate_scene(
                yacht_id=yacht_id,
                source=source,
                scene_id=action.scene_id,
            )
            alarm_service.sync_all(yacht_id)
        except (KeyError, ValueError) as exc:
            return _result(action.action_id, "rejected", str(exc))

        return AICommandResultItem(
            action_id=action.action_id,
            status="executed",
            reason="Approved and executed by operator.",
            executed_as=AIExecutedAction(
                type="activate_scene",
                scene_id=action.scene_id,
                source=source,
            ),
        )

    if action.type == "no_op":
        return AICommandResultItem(
            action_id=action.action_id,
            status="executed",
            reason="No-op acknowledged by operator.",
            executed_as=AIExecutedAction(type="no_op", source=source),
        )

    return _result(action.action_id, "rejected", f"Action type '{action.type}' is not supported.")


def _execute_action(
    yacht_id: str,
    action: Any,
    devices: Dict[str, Device],
    mode: str,
) -> AICommandResultItem:
    if action.type == "no_op":
        return AICommandResultItem(
            action_id=action.action_id,
            status="executed",
            reason="No-op acknowledged",
            executed_as=AIExecutedAction(type="no_op", source="ai_watchkeeper"),
        )

    if action.type == "set_device_state":
        return _execute_device_action(yacht_id, action, devices)

    if action.type == "activate_scene":
        return _execute_scene_action(yacht_id, action, mode)

    return AICommandResultItem(
        action_id=action.action_id,
        status="rejected",
        reason=f"Action type '{action.type}' is not supported.",
    )


def _execute_device_action(
    yacht_id: str,
    action: Any,
    devices: Dict[str, Device],
) -> AICommandResultItem:
    device_id = action.device_id
    if not device_id:
        return _result(action.action_id, "rejected", "Missing device_id.")

    device = devices.get(device_id)
    if device is None:
        return _result(action.action_id, "rejected", f"Device '{device_id}' not found.")

    policy_status, policy_reason = _device_policy(device, action)
    if policy_status != "execute":
        return _result(action.action_id, policy_status, policy_reason)

    failed_condition = _failed_condition(action.constraints, devices)
    if failed_condition:
        return _result(action.action_id, "rejected", failed_condition)

    try:
        device_service.set_device_state(
            yacht_id=yacht_id,
            source="ai_watchkeeper",
            device_id=device_id,
            state=action.target_state,
        )
    except ValueError as exc:
        return _result(action.action_id, "rejected", str(exc))
    except KeyError:
        return _result(action.action_id, "rejected", f"Device '{device_id}' not found.")

    return AICommandResultItem(
        action_id=action.action_id,
        status="executed",
        reason="Executed by AI within policy.",
        executed_as=AIExecutedAction(
            type="set_device_state",
            device_id=device_id,
            target_state=action.target_state,
            source="ai_watchkeeper",
        ),
    )


def _execute_scene_action(yacht_id: str, action: Any, mode: str) -> AICommandResultItem:
    scene_id = action.scene_id
    if not scene_id:
        return _result(action.action_id, "rejected", "Missing scene_id.")

    if mode == "underway" and scene_id == "at_anchor":
        return _result(action.action_id, "rejected", "Refusing at_anchor while underway.")

    if _priority_value(action.priority) < 3 and not str(action.action_id).startswith("rule-"):
        return _result(
            action.action_id,
            "deferred",
            f"Scene '{scene_id}' needs a high-priority safety command.",
        )

    try:
        scene_service.activate_scene(
            yacht_id=yacht_id,
            source="ai_watchkeeper",
            scene_id=scene_id,
        )
    except KeyError:
        return _result(action.action_id, "rejected", f"Scene '{scene_id}' not found.")
    except ValueError as exc:
        return _result(action.action_id, "rejected", str(exc))

    return AICommandResultItem(
        action_id=action.action_id,
        status="executed",
        reason="Scene activated by AI within policy.",
        executed_as=AIExecutedAction(
            type="activate_scene",
            scene_id=scene_id,
            source="ai_watchkeeper",
        ),
    )


def _device_policy(device: Device, action: Any) -> tuple[str, str]:
    if device.type == DeviceType.SENSOR:
        return "rejected", f"Device '{device.id}' is a sensor and cannot be controlled."

    if _is_bilge_safety_rule(device, action):
        return "execute", "Bilge safety rule accepted."

    if device.ai_control == AiControlLevel.NEVER:
        return "rejected", f"Device '{device.id}' is not AI-controllable."

    if device.control_authority in {"manual", "ai_suggest_only"}:
        return "deferred", f"Device '{device.id}' is suggestion-only for AI."

    if device.control_authority == "locked_out":
        return "rejected", f"Device '{device.id}' is locked out."

    if device.ai_control == AiControlLevel.LIMITED and _priority_value(action.priority) < 3:
        return "deferred", f"Device '{device.id}' needs a high-priority safety command."

    return "execute", "Allowed."


def _is_bilge_safety_rule(device: Device, action: Any) -> bool:
    return (
        device.id == "bilge_pump_auto_override"
        and str(action.action_id).startswith("rule-bilge")
        and _priority_value(action.priority) >= 3
    )


def _failed_condition(constraints: Optional[Dict[str, Any]], devices: Dict[str, Device]) -> Optional[str]:
    if not constraints:
        return None

    only_if = constraints.get("only_if") or {}
    if isinstance(only_if, dict) and "device_state_equals" in only_if:
        expected_states = only_if.get("device_state_equals") or {}
    else:
        expected_states = only_if

    if not isinstance(expected_states, dict):
        return None

    for device_id, expected in expected_states.items():
        device = devices.get(device_id)
        if device is None or device.state != expected:
            return f"Condition failed: {device_id} != {expected!r}."
    return None


def _priority_value(priority: Any) -> int:
    if isinstance(priority, int):
        return priority

    priorities = {
        "info": 0,
        "low": 1,
        "normal": 2,
        "high": 3,
        "critical": 4,
    }
    return priorities.get(str(priority or "normal").lower(), 2)


def _infer_mode(devices: List[Device]) -> str:
    by_id = {d.id: d for d in devices}
    anchor_on = by_id.get("anchor_light") and by_id["anchor_light"].state is True
    nav_on = by_id.get("nav_lights") and by_id["nav_lights"].state is True

    if nav_on:
        return "underway"
    if anchor_on:
        return "anchor"
    return "in_port"


def _build_suggestions(devices: Dict[str, Device], mode: str) -> List[Dict[str, Any]]:
    suggestions: List[Dict[str, Any]] = []

    def add(
        suggestion_id: str,
        title: str,
        reason: str,
        device_id: str,
        target_state: bool,
        priority: str = "normal",
    ) -> None:
        device = devices.get(device_id)
        if device is None or device.state is target_state:
            return
        suggestions.append(
            {
                "id": suggestion_id,
                "title": title,
                "reason": reason,
                "priority": priority,
                "action": {
                    "action_id": suggestion_id,
                    "type": "set_device_state",
                    "device_id": device_id,
                    "target_state": target_state,
                    "priority": priority,
                    "reason": reason,
                },
            }
        )

    bilge = devices.get("bilge_float_high")
    if bilge and bilge.state is True:
        add(
            "suggest-bilge-pump",
            "Enable bilge pump override",
            "Bilge high float is active.",
            "bilge_pump_auto_override",
            True,
            "critical",
        )

    house = devices.get("battery_voltage_house")
    if house and isinstance(house.state, (int, float)) and house.state < 11.8:
        for device_id in ["inverter_power", "cabin_heater", "fridge"]:
            add(
                f"suggest-shed-{device_id}",
                f"Turn off {device_id.replace('_', ' ')}",
                "House battery voltage is low.",
                device_id,
                False,
                "high",
            )

    if mode == "at_anchor":
        add("suggest-anchor-light", "Turn on anchor light", "At-anchor mode expects anchor light.", "anchor_light", True, "high")
        add("suggest-nav-off", "Turn off navigation lights", "At-anchor mode expects navigation lights off.", "nav_lights", False, "high")
    elif mode == "underway":
        add("suggest-nav-on", "Turn on navigation lights", "Underway mode expects navigation lights.", "nav_lights", True, "high")
        add("suggest-anchor-off", "Turn off anchor light", "Underway mode expects anchor light off.", "anchor_light", False, "high")

    return suggestions


def _result(action_id: str, status: str, reason: str) -> AICommandResultItem:
    return AICommandResultItem(
        action_id=action_id,
        status=status,
        reason=reason,
        executed_as=None,
    )
