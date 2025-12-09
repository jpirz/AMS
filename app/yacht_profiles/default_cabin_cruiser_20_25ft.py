"""
Default I/O profile + device definitions for a 20–25 ft cabin cruiser.

This is a generic profile intended to be reused across multiple small boats.
A specific yacht (e.g. "marex-21-001") can be mapped to this profile in your
config, but this file itself is NOT tied to a single yacht_id.

Logical device IDs are stable and are what the rest of the system uses:
- anchor_light
- nav_lights
- bilge_pump_main
- bilge_pump_auto_override
- bilge_float_high
etc.
"""

PROFILE_ID = "default_cabin_cruiser_20_25ft"

# ---------------------------------------------------------------------------
# DIGITAL OUTPUTS (DO1–DO16)
#
# Convention:
#   DO1  -> nav_lights
#   DO2  -> anchor_light
#   DO3  -> cabin_lights
#   DO4  -> cockpit_lights
#   DO5  -> deck_flood
#   DO6  -> bilge_pump_main
#   DO7  -> fw_pump
#   DO8  -> fridge_12v
#   DO9  -> blower
#   DO10 -> horn
#   DO11 -> wiper
#   DO12 -> bilge_pump_auto_override  (AI hard rules ONLY, not the model)
#   DO13 -> aux_lights
#   DO14 -> custom_output_1
#   DO15 -> custom_output_2
#   DO16 -> custom_output_3
#
# Your hardware layer can map:
#   DO channel N -> modbus coil[N-1] or similar.
# ---------------------------------------------------------------------------

DIGITAL_OUTPUTS = [
    {
        "id": "nav_lights",
        "name": "Navigation Lights",
        "type": "light",
        "zone": "EXTERIOR",
        "io": {"kind": "do", "channel": 1},
        "ai_control": True,     # AI COLREGs rules allowed
    },
    {
        "id": "anchor_light",
        "name": "Anchor Light",
        "type": "light",
        "zone": "EXTERIOR",
        "io": {"kind": "do", "channel": 2},
        "ai_control": True,     # AI COLREGs rules allowed
    },
    {
        "id": "cabin_lights",
        "name": "Cabin Lights",
        "type": "light",
        "zone": "CABIN",
        "io": {"kind": "do", "channel": 3},
        "ai_control": False,
    },
    {
        "id": "cockpit_lights",
        "name": "Cockpit Lights",
        "type": "light",
        "zone": "COCKPIT",
        "io": {"kind": "do", "channel": 4},
        "ai_control": False,
    },
    {
        "id": "deck_flood",
        "name": "Deck Floodlight",
        "type": "light",
        "zone": "DECK",
        "io": {"kind": "do", "channel": 5},
        "ai_control": False,
    },
    {
        "id": "bilge_pump_main",
        "name": "Bilge Pump – Main",
        "type": "pump",
        "zone": "BILGE",
        "io": {"kind": "do", "channel": 6},
        "ai_control": False,    # controlled via float + override logic
    },
    {
        "id": "fw_pump",
        "name": "Fresh Water Pump",
        "type": "pump",
        "zone": "SYSTEMS",
        "io": {"kind": "do", "channel": 7},
        "ai_control": False,
    },
    {
        "id": "fridge_12v",
        "name": "Fridge 12V",
        "type": "load",
        "zone": "GALLEY",
        "io": {"kind": "do", "channel": 8},
        "ai_control": False,
    },
    {
        "id": "blower",
        "name": "Engine Room Blower",
        "type": "fan",
        "zone": "ENGINE_ROOM",
        "io": {"kind": "do", "channel": 9},
        "ai_control": False,
    },
    {
        "id": "horn",
        "name": "Horn",
        "type": "aux",
        "zone": "HELM",
        "io": {"kind": "do", "channel": 10},
        "ai_control": False,
    },
    {
        "id": "wiper",
        "name": "Wiper",
        "type": "aux",
        "zone": "HELM",
        "io": {"kind": "do", "channel": 11},
        "ai_control": False,
    },
    {
        # Critical: used by deterministic AI bilge safety rules
        "id": "bilge_pump_auto_override",
        "name": "Bilge Pump Auto Override",
        "type": "pump_control",
        "zone": "BILGE",
        "io": {"kind": "do", "channel": 12},
        "ai_control": True,   # needed so hard rules in ai_watchkeeper can toggle it
    },
    {
        "id": "aux_lights",
        "name": "Auxiliary Lights",
        "type": "light",
        "zone": "EXTERIOR",
        "io": {"kind": "do", "channel": 13},
        "ai_control": False,
    },
    {
        "id": "custom_output_1",
        "name": "Custom Output 1",
        "type": "aux",
        "zone": "CUSTOM",
        "io": {"kind": "do", "channel": 14},
        "ai_control": False,
    },
    {
        "id": "custom_output_2",
        "name": "Custom Output 2",
        "type": "aux",
        "zone": "CUSTOM",
        "io": {"kind": "do", "channel": 15},
        "ai_control": False,
    },
    {
        "id": "custom_output_3",
        "name": "Custom Output 3",
        "type": "aux",
        "zone": "CUSTOM",
        "io": {"kind": "do", "channel": 16},
        "ai_control": False,
    },
]

# ---------------------------------------------------------------------------
# DIGITAL INPUTS (DI1–DI16)
#
# DI1  -> nav_switch
# DI2  -> anchor_switch
# DI3  -> cabin_light_switch
# DI4  -> cockpit_light_switch
# DI5  -> bilge_float_high
# DI6  -> bilge_float_low
# DI7  -> shore_power_present
# DI8  -> ignition_on
# DI9  -> engine_running
# DI10 -> door_reed_cabin
# DI11 -> smoke_fire_alarm
# DI12 -> co_alarm
# DI13–DI16 -> custom digital inputs
# ---------------------------------------------------------------------------

DIGITAL_INPUTS = [
    {
        "id": "nav_switch",
        "name": "Nav Lights Switch",
        "type": "switch",
        "zone": "HELM",
        "io": {"kind": "di", "channel": 1},
    },
    {
        "id": "anchor_switch",
        "name": "Anchor Light Switch",
        "type": "switch",
        "zone": "HELM",
        "io": {"kind": "di", "channel": 2},
    },
    {
        "id": "cabin_light_switch",
        "name": "Cabin Lights Switch",
        "type": "switch",
        "zone": "CABIN",
        "io": {"kind": "di", "channel": 3},
    },
    {
        "id": "cockpit_light_switch",
        "name": "Cockpit Lights Switch",
        "type": "switch",
        "zone": "COCKPIT",
        "io": {"kind": "di", "channel": 4},
    },
    {
        # Used by AI bilge logic (with latch)
        "id": "bilge_float_high",
        "name": "Bilge Float – High",
        "type": "sensor",
        "zone": "BILGE",
        "io": {"kind": "di", "channel": 5},
    },
    {
        "id": "bilge_float_low",
        "name": "Bilge Float – Low",
        "type": "sensor",
        "zone": "BILGE",
        "io": {"kind": "di", "channel": 6},
    },
    {
        "id": "shore_power_present",
        "name": "Shore Power Present",
        "type": "sensor",
        "zone": "ELECTRICAL",
        "io": {"kind": "di", "channel": 7},
    },
    {
        "id": "ignition_on",
        "name": "Ignition On",
        "type": "sensor",
        "zone": "ENGINE_ROOM",
        "io": {"kind": "di", "channel": 8},
    },
    {
        "id": "engine_running",
        "name": "Engine Running",
        "type": "sensor",
        "zone": "ENGINE_ROOM",
        "io": {"kind": "di", "channel": 9},
    },
    {
        "id": "door_reed_cabin",
        "name": "Cabin Door Reed",
        "type": "sensor",
        "zone": "CABIN",
        "io": {"kind": "di", "channel": 10},
    },
    {
        "id": "smoke_fire_alarm",
        "name": "Smoke / Fire Alarm",
        "type": "alarm",
        "zone": "CABIN",
        "io": {"kind": "di", "channel": 11},
    },
    {
        "id": "co_alarm",
        "name": "CO Alarm",
        "type": "alarm",
        "zone": "CABIN",
        "io": {"kind": "di", "channel": 12},
    },
    {
        "id": "custom_input_1",
        "name": "Custom Input 1",
        "type": "sensor",
        "zone": "CUSTOM",
        "io": {"kind": "di", "channel": 13},
    },
    {
        "id": "custom_input_2",
        "name": "Custom Input 2",
        "type": "sensor",
        "zone": "CUSTOM",
        "io": {"kind": "di", "channel": 14},
    },
    {
        "id": "custom_input_3",
        "name": "Custom Input 3",
        "type": "sensor",
        "zone": "CUSTOM",
        "io": {"kind": "di", "channel": 15},
    },
    {
        "id": "custom_input_4",
        "name": "Custom Input 4",
        "type": "sensor",
        "zone": "CUSTOM",
        "io": {"kind": "di", "channel": 16},
    },
]

# ---------------------------------------------------------------------------
# ANALOG INPUTS (AI1–AI8)
#
# AI1  -> house_batt_v
# AI2  -> start_batt_v
# AI3  -> fuel_level
# AI4  -> fresh_water_level
# AI5  -> engine_temp
# AI6  -> cabin_temp
# AI7  -> custom_ain_1
# AI8  -> custom_ain_2
# ---------------------------------------------------------------------------

ANALOG_INPUTS = [
    {
        "id": "house_batt_v",
        "name": "House Battery Voltage",
        "type": "analog",
        "zone": "ELECTRICAL",
        "io": {"kind": "ai", "channel": 1},
    },
    {
        "id": "start_batt_v",
        "name": "Start Battery Voltage",
        "type": "analog",
        "zone": "ELECTRICAL",
        "io": {"kind": "ai", "channel": 2},
    },
    {
        "id": "fuel_level",
        "name": "Fuel Level",
        "type": "tank",
        "zone": "TANKS",
        "io": {"kind": "ai", "channel": 3},
    },
    {
        "id": "fresh_water_level",
        "name": "Fresh Water Level",
        "type": "tank",
        "zone": "TANKS",
        "io": {"kind": "ai", "channel": 4},
    },
    {
        "id": "engine_temp",
        "name": "Engine Temperature",
        "type": "analog",
        "zone": "ENGINE_ROOM",
        "io": {"kind": "ai", "channel": 5},
    },
    {
        "id": "cabin_temp",
        "name": "Cabin Temperature",
        "type": "analog",
        "zone": "CABIN",
        "io": {"kind": "ai", "channel": 6},
    },
    {
        "id": "custom_ain_1",
        "name": "Custom Analog 1",
        "type": "analog",
        "zone": "CUSTOM",
        "io": {"kind": "ai", "channel": 7},
    },
    {
        "id": "custom_ain_2",
        "name": "Custom Analog 2",
        "type": "analog",
        "zone": "CUSTOM",
        "io": {"kind": "ai", "channel": 8},
    },
]

# ---------------------------------------------------------------------------
# COMBINED DEVICE LIST
# ---------------------------------------------------------------------------

DEVICE_DEFINITIONS = DIGITAL_OUTPUTS + DIGITAL_INPUTS + ANALOG_INPUTS


def get_devices_for_profile(profile_id: str = PROFILE_ID):
    """
    Return the device definitions for this profile.

    You can ignore the profile_id argument and just call
    get_devices_for_profile() if you only have one default profile.
    """
    if profile_id != PROFILE_ID:
        raise ValueError(f"Unknown profile_id={profile_id!r}")
    return DEVICE_DEFINITIONS
