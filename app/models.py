from enum import Enum
from pydantic import BaseModel
from typing import Optional, Any, List, Dict
from datetime import datetime


class DeviceType(str, Enum):
    LIGHT = "light"
    PUMP = "pump"
    SWITCH = "switch"
    SENSOR = "sensor"


class AiControlLevel(str, Enum):
    NEVER = "never"
    LIMITED = "limited"
    ALLOWED = "allowed"


class Yacht(BaseModel):
    id: str
    name: str


class Device(BaseModel):
    yacht_id: str
    id: str
    name: str
    zone: str
    type: DeviceType
    state: Optional[Any] = None
    hw_id: Optional[str] = None
    ai_control: AiControlLevel = AiControlLevel.LIMITED
    max_runtime_seconds: Optional[int] = None
    requires_human_ack: bool = False


class SceneAction(BaseModel):
    device_id: str
    state: Any


class Scene(BaseModel):
    yacht_id: str
    id: str
    name: str
    description: Optional[str] = None
    actions: List[SceneAction]


class AiMode(str, Enum):
    DISABLED = "disabled"
    MONITOR = "monitor"
    ASSIST = "assist"
    AUTONOMOUS = "autonomous"


class Event(BaseModel):
    yacht_id: str
    timestamp: datetime
    source: str
    type: str
    details: Dict[str, Any]
