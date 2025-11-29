# app/ai/schemas.py

from __future__ import annotations
from typing import List, Optional, Dict, Literal, Union
from pydantic import BaseModel, Field
from datetime import datetime


StateValue = Union[bool, float, int, str, None]


class AIDevice(BaseModel):
    id: str
    name: str
    type: str                     # "sensor" | "light" | "pump" | "relay" | ...
    zone: Optional[str] = None
    state: StateValue = None
    is_alarm_source: bool = False
    tags: List[str] = Field(default_factory=list)


class AIAlarm(BaseModel):
    alarm_id: str
    severity: Literal["info", "warning", "critical"]
    status: Literal["active", "cleared"]
    source_device_ids: List[str]
    first_raised_at: datetime
    last_changed_at: datetime


class AIEvent(BaseModel):
    timestamp: datetime
    type: str                     # "device_state_change" | "scene_activate" | "alarm" | ...
    source: str                   # "web_ui" | "ai_watchkeeper" | "modbus" | ...
    device_id: Optional[str] = None
    scene_id: Optional[str] = None
    details: Dict[str, StateValue] = Field(default_factory=dict)


class AIEnv(BaseModel):
    now_local: datetime
    time_of_day: Literal["day", "dusk", "night"]
    location_hint: Optional[str] = None


class AIStateSnapshot(BaseModel):
    yacht_id: str
    snapshot_timestamp: datetime

    mode: Optional[str] = None             # "underway" | "at_anchor" | ...
    active_scenes: List[str] = Field(default_factory=list)

    devices: List[AIDevice]
    derived_alarms: List[AIAlarm] = Field(default_factory=list)
    recent_events: List[AIEvent] = Field(default_factory=list)

    env: Optional[AIEnv] = None


# ---------- Commands from AI ----------

class AIActionConditions(BaseModel):
    device_state_equals: Dict[str, StateValue] = Field(default_factory=dict)


class AIActionConstraints(BaseModel):
    max_duration_seconds: Optional[int] = None
    min_off_cooldown_seconds: Optional[int] = None
    auto_revert: Optional[bool] = None
    confirmation_required: Optional[bool] = None
    only_if: Optional[AIActionConditions] = None


class AICommandAction(BaseModel):
    action_id: str
    type: Literal["set_device_state", "activate_scene", "deactivate_scene", "no_op"]
    device_id: Optional[str] = None
    scene_id: Optional[str] = None
    target_state: Optional[StateValue] = None
    priority: Literal["info", "normal", "critical"] = "normal"
    constraints: Optional[AIActionConstraints] = None
    reason: Optional[str] = None


class AICommandRequest(BaseModel):
    yacht_id: str
    request_id: str
    requested_by: Literal["ai_watchkeeper"] = "ai_watchkeeper"
    generated_at: datetime
    intent_summary: Optional[str] = None
    actions: List[AICommandAction]


class AIExecutedAction(BaseModel):
    type: Literal["set_device_state", "activate_scene", "deactivate_scene", "no_op"]
    device_id: Optional[str] = None
    scene_id: Optional[str] = None
    target_state: Optional[StateValue] = None
    source: str


class AICommandResultItem(BaseModel):
    action_id: str
    status: Literal["executed", "rejected", "deferred"]
    reason: str
    executed_as: Optional[AIExecutedAction] = None


class AICommandResponse(BaseModel):
    request_id: str
    yacht_id: str
    processed_at: datetime
    results: List[AICommandResultItem]
