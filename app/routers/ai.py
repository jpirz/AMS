# app/routers/ai.py
import json
from typing import Any, Dict, List, Optional, Literal
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from openai import OpenAI

from app.db import get_connection
from app.services.device_service_sql import DeviceService
from app.services.scene_service_sql import SceneService
from app.services.event_service_sql import EventLogger
from app.hardware.manager import HardwareManager
from app.services.system_state_sql import SystemState  # NEW

router = APIRouter(prefix="/yachts/{yacht_id}/ai", tags=["ai"])

# OpenAI client for chat endpoint (uses OPENAI_API_KEY)
client = OpenAI()

# System state service (for ai_mode)
_system_state = SystemState()


# ---------- MODELS FOR AI COMMANDS ----------


class AIAction(BaseModel):
  action_id: str
  type: Literal["set_device_state", "activate_scene", "no_op"]
  device_id: Optional[str] = None
  scene_id: Optional[str] = None
  target_state: Optional[Any] = None
  priority: Optional[str] = "info"
  constraints: Dict[str, Any] = {}
  reason: Optional[str] = None


class AICommandRequest(BaseModel):
  yacht_id: str
  request_id: str
  requested_by: str
  generated_at: str
  actions: List[AIAction]


# ---------- MODELS FOR AI WATCHKEEPER LOGS ----------


class AIWatchLog(BaseModel):
  generated_at: str
  summary: str
  actions: List[Dict[str, Any]]
  mode: Optional[str] = None


# ---------- MODELS FOR AI CHAT ----------


class AIChatRequest(BaseModel):
  message: str


class AIChatResponse(BaseModel):
  reply: str
  created_at: str


# ---------- SNAPSHOT (same behaviour, now includes ai_mode) ----------


@router.get("/state_snapshot")
async def get_state_snapshot(yacht_id: str) -> Dict[str, Any]:
  """
  Lightweight snapshot for the AI watchkeeper:
  - All devices for this yacht
  - Recent events (last 100)
  - Current ai_mode from system_state
  """
  conn = get_connection()
  try:
    # Devices
    d_cur = conn.execute(
      """
      SELECT id, name, zone, type, state, ai_control,
             max_runtime_seconds, requires_human_ack
      FROM devices
      WHERE yacht_id = ?
      """,
      (yacht_id,),
    )
    device_rows = d_cur.fetchall()

    # Events (recent)
    e_cur = conn.execute(
      """
      SELECT timestamp, source, type, details
      FROM events
      WHERE yacht_id = ?
      ORDER BY timestamp DESC
      LIMIT 100
      """,
      (yacht_id,),
    )
    event_rows = e_cur.fetchall()
  finally:
    conn.close()

  devices: List[Dict[str, Any]] = []
  for r in device_rows:
    state = json.loads(r["state"]) if r["state"] is not None else None
    devices.append(
      {
        "id": r["id"],
        "name": r["name"],
        "zone": r["zone"],
        "type": r["type"],
        "state": state,
        "ai_control": r["ai_control"],
        "max_runtime_seconds": r["max_runtime_seconds"],
        "requires_human_ack": bool(r["requires_human_ack"]),
      }
    )

  events: List[Dict[str, Any]] = []
  for r in event_rows:
    details = json.loads(r["details"]) if r["details"] else None
    events.append(
      {
        "timestamp": r["timestamp"],
        "source": r["source"],
        "type": r["type"],
        "details": details,
      }
    )

  # NEW: include ai_mode so the watchkeeper knows how much autonomy it has
  ai_mode = _system_state.get_ai_mode(yacht_id)

  return {
    "yacht_id": yacht_id,
    "ai_mode": ai_mode.value,
    "devices": devices,
    "events": events,
  }


# ---------- COMMAND APPLICATION (same logic, 500 fix kept) ----------


@router.post("/commands")
async def apply_ai_commands(yacht_id: str, cmd: AICommandRequest) -> Dict[str, Any]:
  """
  Apply AI-requested actions in a very conservative way:
  - ignore 'no_op'
  - only touch devices with ai_control = 1
  - only apply boolean states to non-sensor devices (enforced by DeviceService)
  """
  if cmd.yacht_id != yacht_id:
    raise HTTPException(status_code=400, detail="yacht_id mismatch")

  # Local service instances for this request
  hw_manager = HardwareManager()
  event_logger = EventLogger()
  device_service = DeviceService(hw_manager, event_logger)
  scene_service = SceneService(device_service, event_logger)

  applied: List[str] = []

  for action in cmd.actions:
    # Skip no-op actions
    if action.type == "no_op":
      continue

    if action.type == "set_device_state" and action.device_id:
      try:
        dev = device_service.get_device(yacht_id, action.device_id)
      except KeyError:
        # Device doesn't exist, skip
        continue

      # Respect per-device AI enable flag
      if not dev.ai_control:
        continue

      # Only boolean states for now (pumps, lights, etc.)
      if isinstance(action.target_state, bool):
        device_service.set_device_state(
          yacht_id=yacht_id,
          source=f"ai:{cmd.request_id}",
          device_id=action.device_id,
          state=action.target_state,
        )
        applied.append(action.action_id)

    elif action.type == "activate_scene" and action.scene_id:
      # We allow AI to trigger scenes (e.g. night_mode, at_anchor)
      scene_service.activate_scene(
        yacht_id=yacht_id,
        source=f"ai:{cmd.request_id}",
        scene_id=action.scene_id,
      )
      applied.append(action.action_id)

  # Log the whole AI decision for auditing
  event_logger.log(
    yacht_id=yacht_id,
    source=f"ai:{cmd.request_id}",
    type="ai_commands",
    details={
      "request_id": cmd.request_id,
      "generated_at": cmd.generated_at,
      "requested_by": cmd.requested_by,
      "actions": [a.model_dump() for a in cmd.actions],
      "applied": applied,
    },
  )

  return {"applied": applied}


# ---------- AI WATCHKEEPER LOG STORAGE (used by ai_watchkeeper.py + UI) ----------


@router.post("/logs")
async def add_ai_log(yacht_id: str, log: AIWatchLog) -> Dict[str, str]:
  """
  Store a human-readable log entry from the ai_watchkeeper.
  Reuses the events table with type='ai_log'.
  """
  conn = get_connection()
  try:
    conn.execute(
      """
      INSERT INTO events (yacht_id, timestamp, source, type, details)
      VALUES (?, ?, ?, ?, ?)
      """,
      (
        yacht_id,
        log.generated_at,
        "ai_watchkeeper",
        "ai_log",
        json.dumps(
          {
            "summary": log.summary,
            "actions": log.actions,
            "mode": log.mode,
          }
        ),
      ),
    )
    conn.commit()
  finally:
    conn.close()

  return {"status": "ok"}


@router.get("/logs")
async def get_ai_logs(
  yacht_id: str,
  limit: int = 50,
) -> List[Dict[str, Any]]:
  """
  Return recent AI watchkeeper log entries for the UI.
  """
  conn = get_connection()
  try:
    cur = conn.execute(
      """
      SELECT timestamp, details
      FROM events
      WHERE yacht_id = ? AND type = 'ai_log'
      ORDER BY timestamp DESC
      LIMIT ?
      """,
      (yacht_id, limit),
    )
    rows = cur.fetchall()
  finally:
    conn.close()

  logs: List[Dict[str, Any]] = []
  for r in rows:
    details = json.loads(r["details"] or "{}")
    logs.append(
      {
        "generated_at": r["timestamp"],
        "summary": details.get("summary") or "",
        "actions": details.get("actions") or [],
        "mode": details.get("mode"),
      }
    )

  return logs


# ---------- AI CHAT ENDPOINT (unchanged behaviour) ----------


@router.post("/chat", response_model=AIChatResponse)
async def ai_chat(yacht_id: str, body: AIChatRequest) -> AIChatResponse:
  """
  Simple chat with the AI watchkeeper.
  - Uses recent AI logs as context.
  - Answers in human language.
  """
  # Pull recent AI logs as context
  conn = get_connection()
  try:
    cur = conn.execute(
      """
      SELECT timestamp, details
      FROM events
      WHERE yacht_id = ? AND type = 'ai_log'
      ORDER BY timestamp DESC
      LIMIT 10
      """,
      (yacht_id,),
    )
    rows = cur.fetchall()
  finally:
    conn.close()

  summaries: List[str] = []
  for r in rows:
    details = json.loads(r["details"] or "{}")
    summary = details.get("summary")
    if summary:
      summaries.append(f"{r['timestamp']}: {summary}")

  context_text = "\n".join(summaries) if summaries else "No prior AI logs yet."

  completion = client.chat.completions.create(
    model="gpt-5-nano",
    messages=[
      {
        "role": "system",
        "content": (
          "You are an AI watchkeeper for a small yacht. "
          "You are answering questions from the skipper. "
          "Be concise, clear and use human language instead of technical jargon. "
          "If you are not certain about something, say so."
        ),
      },
      {
        "role": "user",
        "content": (
          "Recent AI watchkeeper logs:\n"
          f"{context_text}\n\n"
          f"Skipper's question: {body.message}"
        ),
      },
    ],
  )

  reply = completion.choices[0].message.content.strip()
  created_at = datetime.now(timezone.utc).isoformat()

  # Store the Q&A as an event for history
  conn = get_connection()
  try:
    conn.execute(
      """
      INSERT INTO events (yacht_id, timestamp, source, type, details)
      VALUES (?, ?, ?, ?, ?)
      """,
      (
        yacht_id,
        created_at,
        "ai_chat",
        "ai_chat",
        json.dumps({"question": body.message, "answer": reply}),
      ),
    )
    conn.commit()
  finally:
    conn.close()

  return AIChatResponse(reply=reply, created_at=created_at)
