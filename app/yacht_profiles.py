# app/yacht_profiles.py

from __future__ import annotations

import json
import copy
from typing import Dict, List, Any

# -------------------------------------------------------
# Raw JSON profile for the default 20–25ft cabin cruiser
# -------------------------------------------------------

_DEFAULT_PROFILE_JSON = r"""
{
  "yacht": {
    "id": "marex-21-001",
    "name": "Marex Flexi 21 #001"
  },
  "hardware": {
    "buses": [
      {
        "id": "io_main",
        "type": "modbus_tcp",
        "vendor": "generic",
        "host": "192.168.10.50",
        "port": 502,
        "unit_id": 1
      }
    ]
  },
  "devices": [
    {
      "id": "salon_lights",
      "name": "Salon Lights",
      "zone": "Salon",
      "type": "light",
      "state": false,
      "hw_id": "modbus:io_main:coil:0",
      "ai_control": "allowed",
      "max_runtime_seconds": null,
      "requires_human_ack": false
    },
    {
      "id": "cabin_lights",
      "name": "Cabin Lights",
      "zone": "Cabin",
      "type": "light",
      "state": false,
      "hw_id": "modbus:io_main:coil:1",
      "ai_control": "allowed",
      "max_runtime_seconds": null,
      "requires_human_ack": false
    },
    {
      "id": "cockpit_lights",
      "name": "Cockpit Lights",
      "zone": "Cockpit",
      "type": "light",
      "state": false,
      "hw_id": "modbus:io_main:coil:2",
      "ai_control": "allowed",
      "max_runtime_seconds": null,
      "requires_human_ack": false
    },
    {
      "id": "nav_lights",
      "name": "Navigation Lights (port/starboard/stern)",
      "zone": "Exterior",
      "type": "light",
      "state": false,
      "hw_id": "modbus:io_main:coil:3",
      "ai_control": "limited",
      "max_runtime_seconds": null,
      "requires_human_ack": true
    },
    {
      "id": "anchor_light",
      "name": "Anchor Light",
      "zone": "Mast",
      "type": "light",
      "state": false,
      "hw_id": "modbus:io_main:coil:4",
      "ai_control": "limited",
      "max_runtime_seconds": null,
      "requires_human_ack": true
    },
    {
      "id": "deck_flood_light",
      "name": "Foredeck Flood Light",
      "zone": "Foredeck",
      "type": "light",
      "state": false,
      "hw_id": "modbus:io_main:coil:5",
      "ai_control": "allowed",
      "max_runtime_seconds": null,
      "requires_human_ack": false
    },
    {
      "id": "courtesy_lights",
      "name": "Courtesy / Step Lights",
      "zone": "Cockpit/Side Decks",
      "type": "light",
      "state": false,
      "hw_id": "modbus:io_main:coil:6",
      "ai_control": "allowed",
      "max_runtime_seconds": null,
      "requires_human_ack": false
    },
    {
      "id": "freshwater_pump",
      "name": "Fresh Water Pump",
      "zone": "Technical",
      "type": "pump",
      "state": false,
      "hw_id": "modbus:io_main:coil:7",
      "ai_control": "limited",
      "max_runtime_seconds": 600,
      "requires_human_ack": false
    },
    {
      "id": "shower_sump_pump",
      "name": "Shower Sump Pump",
      "zone": "Cabin / Bilge",
      "type": "pump",
      "state": false,
      "hw_id": "modbus:io_main:coil:8",
      "ai_control": "limited",
      "max_runtime_seconds": 600,
      "requires_human_ack": false
    },
    {
      "id": "bilge_pump_main",
      "name": "Main Bilge Pump",
      "zone": "Bilge",
      "type": "pump",
      "state": false,
      "hw_id": "modbus:io_main:coil:9",
      "ai_control": "limited",
      "max_runtime_seconds": 600,
      "requires_human_ack": true
    },
    {
      "id": "bilge_pump_auto_override",
      "name": "Bilge Auto Override",
      "zone": "Bilge",
      "type": "switch",
      "state": false,
      "hw_id": "modbus:io_main:coil:10",
      "ai_control": "never",
      "max_runtime_seconds": null,
      "requires_human_ack": true
    },
    {
      "id": "fridge",
      "name": "Fridge",
      "zone": "Galley",
      "type": "switch",
      "state": false,
      "hw_id": "modbus:io_main:coil:11",
      "ai_control": "limited",
      "max_runtime_seconds": null,
      "requires_human_ack": false
    },
    {
      "id": "cabin_fan",
      "name": "Cabin Ventilation Fan",
      "zone": "Cabin",
      "type": "switch",
      "state": false,
      "hw_id": "modbus:io_main:coil:12",
      "ai_control": "allowed",
      "max_runtime_seconds": null,
      "requires_human_ack": false
    },
    {
      "id": "windscreen_wiper",
      "name": "Windscreen Wiper",
      "zone": "Helm",
      "type": "switch",
      "state": false,
      "hw_id": "modbus:io_main:coil:13",
      "ai_control": "never",
      "max_runtime_seconds": null,
      "requires_human_ack": true
    },
    {
      "id": "horn",
      "name": "Horn",
      "zone": "Helm",
      "type": "switch",
      "state": false,
      "hw_id": "modbus:io_main:coil:14",
      "ai_control": "never",
      "max_runtime_seconds": null,
      "requires_human_ack": true
    },
    {
      "id": "inverter_power",
      "name": "Inverter On/Off",
      "zone": "Technical",
      "type": "switch",
      "state": false,
      "hw_id": "modbus:io_main:coil:15",
      "ai_control": "limited",
      "max_runtime_seconds": null,
      "requires_human_ack": true
    },
    {
      "id": "cabin_heater",
      "name": "Cabin Heater / Diesel Heater",
      "zone": "Cabin/Technical",
      "type": "switch",
      "state": false,
      "hw_id": "modbus:io_main:coil:16",
      "ai_control": "limited",
      "max_runtime_seconds": null,
      "requires_human_ack": true
    },
    {
      "id": "bilge_float_high",
      "name": "Bilge High Level Float",
      "zone": "Bilge",
      "type": "sensor",
      "state": null,
      "hw_id": "modbus:io_main:input:0",
      "ai_control": "never",
      "max_runtime_seconds": null,
      "requires_human_ack": false
    },
    {
      "id": "bilge_float_auto",
      "name": "Bilge Auto Float",
      "zone": "Bilge",
      "type": "sensor",
      "state": null,
      "hw_id": "modbus:io_main:input:1",
      "ai_control": "never",
      "max_runtime_seconds": null,
      "requires_human_ack": false
    },
    {
      "id": "cabin_door_contact",
      "name": "Cabin Door Contact",
      "zone": "Cabin",
      "type": "sensor",
      "state": null,
      "hw_id": "modbus:io_main:input:2",
      "ai_control": "never",
      "max_runtime_seconds": null,
      "requires_human_ack": false
    },
    {
      "id": "engine_room_door_contact",
      "name": "Engine Space Access Hatch",
      "zone": "Engine Room / Aft",
      "type": "sensor",
      "state": null,
      "hw_id": "modbus:io_main:input:3",
      "ai_control": "never",
      "max_runtime_seconds": null,
      "requires_human_ack": false
    },
    {
      "id": "helm_anchor_scene_button",
      "name": "Helm \u201cAt Anchor\u201d Button",
      "zone": "Helm",
      "type": "switch",
      "state": false,
      "hw_id": "modbus:io_main:input:4",
      "ai_control": "never",
      "max_runtime_seconds": null,
      "requires_human_ack": false
    },
    {
      "id": "helm_night_scene_button",
      "name": "Helm \u201cNight Mode\u201d Button",
      "zone": "Helm",
      "type": "switch",
      "state": false,
      "hw_id": "modbus:io_main:input:5",
      "ai_control": "never",
      "max_runtime_seconds": null,
      "requires_human_ack": false
    },
    {
      "id": "shore_power_present",
      "name": "Shore Power Present",
      "zone": "Technical",
      "type": "sensor",
      "state": null,
      "hw_id": "modbus:io_main:input:6",
      "ai_control": "never",
      "max_runtime_seconds": null,
      "requires_human_ack": false
    },
    {
      "id": "battery_low_alarm",
      "name": "Battery Low Alarm Input",
      "zone": "Technical",
      "type": "sensor",
      "state": null,
      "hw_id": "modbus:io_main:input:7",
      "ai_control": "never",
      "max_runtime_seconds": null,
      "requires_human_ack": false
    },
    {
      "id": "fresh_water_tank_level",
      "name": "Fresh Water Tank Level",
      "zone": "Tanks",
      "type": "sensor",
      "state": null,
      "hw_id": "modbus:io_main:holding:0",
      "ai_control": "never",
      "max_runtime_seconds": null,
      "requires_human_ack": false
    },
    {
      "id": "fuel_tank_level",
      "name": "Fuel Tank Level",
      "zone": "Tanks",
      "type": "sensor",
      "state": null,
      "hw_id": "modbus:io_main:holding:1",
      "ai_control": "never",
      "max_runtime_seconds": null,
      "requires_human_ack": false
    },
    {
      "id": "battery_voltage_house",
      "name": "House Battery Voltage",
      "zone": "Electrical",
      "type": "sensor",
      "state": null,
      "hw_id": "modbus:io_main:holding:2",
      "ai_control": "never",
      "max_runtime_seconds": null,
      "requires_human_ack": false
    },
    {
      "id": "battery_voltage_engine",
      "name": "Engine Battery Voltage",
      "zone": "Electrical",
      "type": "sensor",
      "state": null,
      "hw_id": "modbus:io_main:holding:3",
      "ai_control": "never",
      "max_runtime_seconds": null,
      "requires_human_ack": false
    },
    {
      "id": "engine_room_temp",
      "name": "Engine Room Temperature",
      "zone": "Engine Room",
      "type": "sensor",
      "state": null,
      "hw_id": "modbus:io_main:holding:4",
      "ai_control": "never",
      "max_runtime_seconds": null,
      "requires_human_ack": false
    }
  ],
  "scenes": [
    {
      "id": "at_anchor",
      "name": "At Anchor",
      "description": "At anchor configuration: anchor + cockpit + courtesy lights.",
      "actions": [
        { "device_id": "anchor_light", "state": true },
        { "device_id": "cockpit_lights", "state": true },
        { "device_id": "salon_lights", "state": false },
        { "device_id": "courtesy_lights", "state": true },
        { "device_id": "nav_lights", "state": false }
      ]
    },
    {
      "id": "night_mode",
      "name": "Night Mode",
      "description": "Night mode for cabins and courtesy lights.",
      "actions": [
        { "device_id": "salon_lights", "state": false },
        { "device_id": "cabin_lights", "state": true },
        { "device_id": "cockpit_lights", "state": false },
        { "device_id": "courtesy_lights", "state": true }
      ]
    },
    {
      "id": "underway",
      "name": "Underway",
      "description": "Underway running lights configuration.",
      "actions": [
        { "device_id": "nav_lights", "state": true },
        { "device_id": "anchor_light", "state": false },
        { "device_id": "cockpit_lights", "state": true },
        { "device_id": "salon_lights", "state": false }
      ]
    },
    {
      "id": "harbour_mode",
      "name": "In Harbour",
      "description": "Harbour mode lighting.",
      "actions": [
        { "device_id": "nav_lights", "state": false },
        { "device_id": "anchor_light", "state": false },
        { "device_id": "cockpit_lights", "state": true },
        { "device_id": "salon_lights", "state": true },
        { "device_id": "courtesy_lights", "state": true }
      ]
    }
  ]
}
"""

DEFAULT_CABIN_CRUISER_20_25FT: Dict[str, Any] = json.loads(_DEFAULT_PROFILE_JSON)

# -------------------------------------------------------
# Profiles registry
# -------------------------------------------------------

PROFILES: Dict[str, Dict[str, Any]] = {
    "default_cabin_cruiser_20_25ft": DEFAULT_CABIN_CRUISER_20_25FT,
    "marex-21-001": DEFAULT_CABIN_CRUISER_20_25FT,
}


def _get_profile_for_yacht(yacht_id: str) -> Dict[str, Any]:
    if yacht_id in PROFILES:
        return PROFILES[yacht_id]

    base = copy.deepcopy(DEFAULT_CABIN_CRUISER_20_25FT)
    yacht_meta = base.setdefault("yacht", {})
    yacht_meta["id"] = yacht_id
    yacht_meta.setdefault("name", f"Boat {yacht_id}")
    return base


def get_devices_for_yacht(yacht_id: str) -> List[Dict[str, Any]]:
    profile = _get_profile_for_yacht(yacht_id)
    return profile.get("devices", [])


def get_scenes_for_yacht(yacht_id: str) -> List[Dict[str, Any]]:
    profile = _get_profile_for_yacht(yacht_id)
    return profile.get("scenes", [])


def get_yacht_meta(yacht_id: str) -> Dict[str, Any]:
    profile = _get_profile_for_yacht(yacht_id)
    yacht_meta = profile.get("yacht", {}) or {}
    return {
        "id": yacht_meta.get("id", yacht_id),
        "name": yacht_meta.get("name", f"Boat {yacht_id}"),
        "hardware": profile.get("hardware", {}),
    }


def list_known_yachts() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for yacht_id, profile in PROFILES.items():
        meta = profile.get("yacht", {}) or {}
        out.append(
            {
                "id": yacht_id,
                "name": meta.get("name", yacht_id),
            }
        )
    return out
