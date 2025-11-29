# app/ai/policy.py

from __future__ import annotations
from typing import Dict, Any


AI_CONTROL_POLICY: Dict[str, Any] = {
    "devices": {
        "bilge_pump": {
            "level": 2,
            "max_on_duration_seconds": 600,
            "min_off_cooldown_seconds": 30,
            "allowed_modes": ["underway", "at_anchor", "harbour_mode"],
        },
        "battery_low_alarm": {"level": 0},
        "bilge_float_high": {"level": 0},
        "bilge_float_auto": {"level": 0},
        "nav_lights": {
            "level": 1,
            "allowed_modes": ["underway", "at_anchor"],
        },
        "courtesy_lights": {
            "level": 2,
            "allowed_modes": ["at_anchor", "harbour_mode"],
            "max_toggle_per_hour": 20,
        },
        "salon_lights": {"level": 1},
        "cabin_lights": {"level": 0}
    },
    "scenes": {
        "underway": {"level": 1},
        "at_anchor": {"level": 1},
        "harbour_mode": {"level": 2},
        "night_mode": {"level": 1}
    }
}


def get_device_level(device_id: str) -> int:
    cfg = AI_CONTROL_POLICY["devices"].get(device_id)
    return int(cfg["level"]) if cfg else 0


def get_scene_level(scene_id: str) -> int:
    cfg = AI_CONTROL_POLICY["scenes"].get(scene_id)
    return int(cfg["level"]) if cfg else 0
