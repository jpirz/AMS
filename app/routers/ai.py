# app/routers/ai.py

import os
import asyncio
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from openai import OpenAI

router = APIRouter(
    prefix="/yachts/{yacht_id}/ai",
    tags=["ai"],
)

# Internal loopback base URL so the AI endpoints can call existing
# /devices, /events, /scenes without importing their internals.
INTERNAL_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000")

# OpenAI client (uses OPENAI_API_KEY from environment)
client = OpenAI()

# In-memory AI logs: yacht_id -> list[dict]
AI_LOGS: Dict[str, List[Dict[str, Any]]] = {}

# In-memory occupancy state: yacht_id -> "onboard" | "unattended"
OCCUPANCY: Dict[str, str] = {}


# ---------- Models ----------

class AIChatRequest(BaseModel):
    message: str = Field(..., min_length=1)


class AIChatResponse(BaseModel):
    reply: str


class AIWatchLogIn(BaseModel):
    generated_at: datetime
    summary: str
    actions: List[dict] = Field(default_factory=list)
    mode: Optional[str] = None


class AIWatchLogOut(AIWatchLogIn):
    id: str


class AIOccupancyUpdate(BaseModel):
    # Expected values: "onboard" or "unattended"
    occupancy: str = Field(..., pattern="^(onboard|unattended)$")

# ---------- Helpers ----------

async def _fetch_json(client: httpx.AsyncClient, method: str, url: str, **kwargs) -> Any:
    resp = await client.request(method, url, **kwargs)
    resp.raise_for_status()
    return resp.json()


def _init_log_list(yacht_id: str) -> List[Dict[str, Any]]:
    if yacht_id not in AI_LOGS:
        AI_LOGS[yacht_id] = []
    return AI_LOGS[yacht_id]


# ---------- Endpoints ----------

@router.get("/state_snapshot")
async def state_snapshot(yacht_id: str):
    """
    Aggregate current state for the AI watchkeeper:

    - devices: from /yachts/{id}/devices/
    - scenes: from /yachts/{id}/scenes/
    - events: from /yachts/{id}/events?limit=50

    This keeps everything going through the existing device/event logic.

    Also includes:
    - occupancy: "onboard" | "unattended" | "unknown"
    """
    async with httpx.AsyncClient(base_url=INTERNAL_BASE_URL, timeout=5.0) as http:
        devices_task = _fetch_json(http, "GET", f"/yachts/{yacht_id}/devices/")
        scenes_task = _fetch_json(http, "GET", f"/yachts/{yacht_id}/scenes/")
        events_task = _fetch_json(
            http,
            "GET",
            f"/yachts/{yacht_id}/events/",
            params={"limit": 50},
        )

        devices, scenes, events = await asyncio.gather(
            devices_task, scenes_task, events_task
        )

    occupancy = OCCUPANCY.get(yacht_id, "unknown")

    return {
        "yacht": {
            "id": yacht_id,
            "name": yacht_id.replace("-", " ").title(),
        },
        "devices": devices,
        "scenes": scenes,
        "events": events,
        "occupancy": occupancy,
    }


@router.post("/logs", response_model=AIWatchLogOut)
async def add_ai_log(yacht_id: str, log: AIWatchLogIn):
    """
    Called by ai_watchkeeper.py each cycle with a human-readable summary
    and the raw actions. Stored in-memory and used by the UI.
    """
    log_list = _init_log_list(yacht_id)
    log_id = f"log-{len(log_list) + 1:04d}"
    out = {
        "id": log_id,
        "generated_at": log.generated_at,
        "summary": log.summary,
        "actions": log.actions,
        "mode": log.mode,
    }
    log_list.append(out)
    return out


@router.get("/logs", response_model=List[AIWatchLogOut])
async def list_ai_logs(
    yacht_id: str,
    limit: int = Query(50, ge=1, le=200),
):
    """
    Used by the UI to show the AI Watchkeeper log on the "AI Watchkeeper" tab.
    """
    log_list = _init_log_list(yacht_id)
    # newest last in storage, UI is fine with this order
    slice_ = log_list[-limit:]
    return slice_


@router.post("/chat", response_model=AIChatResponse)
async def ai_chat(yacht_id: str, body: AIChatRequest):
    """
    Lightweight AI chat endpoint for the "AI Chat" tab.
    It pulls a small snapshot of current state to give context.
    """
    user_message = body.message.strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="Empty message")

    # Fetch a small context snapshot
    async with httpx.AsyncClient(base_url=INTERNAL_BASE_URL, timeout=5.0) as http:
        devices = await _fetch_json(http, "GET", f"/yachts/{yacht_id}/devices/")
        events = await _fetch_json(
            http,
            "GET",
            f"/yachts/{yacht_id}/events/",
            params={"limit": 10},
        )

    # Keep context reasonably small
    simple_devices = [
        {
            "id": d.get("id"),
            "name": d.get("name"),
            "zone": d.get("zone"),
            "type": d.get("type"),
            "state": d.get("state"),
        }
        for d in devices[:20]
    ]

    simple_events = [
        {
            "timestamp": e.get("timestamp"),
            "type": e.get("type"),
            "source": e.get("source"),
            "details": e.get("details"),
        }
        for e in events[:10]
    ]

    occupancy = OCCUPANCY.get(yacht_id, "unknown")

    system_prompt = (
        "You are the AI watchkeeper for a small yacht.\n"
        "- Be concise and practical.\n"
        "- You can use the current device states, occupancy state, and recent events to answer questions.\n"
        "- occupancy='onboard' means someone is on the boat, so avoid over-automation of comfort devices.\n"
        "- occupancy='unattended' means no one is aboard; you may be proactive about safety and power saving.\n"
        "- If the user asks for instructions, keep them simple and safety-focused.\n"
        "- If you don't know something, say so and avoid guessing.\n"
    )

    context_blob = {
        "yacht_id": yacht_id,
        "occupancy": occupancy,
        "devices": simple_devices,
        "recent_events": simple_events,
    }

    completion = client.chat.completions.create(
        model="gpt-5-nano",
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": (
                    "Current yacht state (JSON):\n"
                    + json_dumps_for_prompt(context_blob)
                    + "\n\nUser question:\n"
                    + user_message
                ),
            },
        ],
    )

    reply_text = completion.choices[0].message.content.strip()
    return AIChatResponse(reply=reply_text)


@router.post("/occupancy")
async def set_occupancy(yacht_id: str, body: AIOccupancyUpdate):
    """
    Called by the UI toggle (Onboard / Unattended).

    Stores occupancy in-memory per yacht:
    - 'onboard'   -> someone is on the boat
    - 'unattended'-> boat is empty, AI can fully manage non-critical systems
    """
    OCCUPANCY[yacht_id] = body.occupancy
    now = datetime.now(timezone.utc).isoformat()
    return {
        "status": "ok",
        "yacht_id": yacht_id,
        "occupancy": body.occupancy,
        "updated_at": now,
    }


# Small helper to keep JSON compact in prompts
def json_dumps_for_prompt(obj: Any) -> str:
    import json
    return json.dumps(obj, separators=(",", ":"), default=str)
