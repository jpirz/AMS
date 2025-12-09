# app/yacht_profiles/__init__.py

from typing import Dict, Any, List

from .default_cabin_cruiser_20_25ft import DEFAULT_CABIN_CRUISER_20_25FT

# -------------------------------------------------------------------
# Profile registry
# -------------------------------------------------------------------
# All known yacht profiles live here.
# Keyed by yacht ID.
# For now we only have one: the default 20–25 ft cabin cruiser profile.
# When you add more boats, import them above and add to PROFILES.

PROFILES: Dict[str, Dict[str, Any]] = {
    DEFAULT_CABIN_CRUISER_20_25FT["yacht"]["id"]: DEFAULT_CABIN_CRUISER_20_25FT,
}

# This is the yacht the system will fall back to if an unknown ID is used.
DEFAULT_YACHT_ID: str = DEFAULT_CABIN_CRUISER_20_25FT["yacht"]["id"]


# -------------------------------------------------------------------
# Core helpers
# -------------------------------------------------------------------

def get_profile(yacht_id: str) -> Dict[str, Any]:
    """
    Return the profile for the given yacht_id, falling back to the default
    profile if the ID is unknown.
    """
    return PROFILES.get(yacht_id, DEFAULT_CABIN_CRUISER_20_25FT)


def get_devices_for_yacht(yacht_id: str) -> List[ Dict[str, Any] ]:
    """
    Helper used by routers to retrieve the device list for a yacht.
    """
    profile = get_profile(yacht_id)
    return profile.get("devices", [])


def get_scenes_for_yacht(yacht_id: str) -> List[ Dict[str, Any] ]:
    """
    Helper for scenes router.
    """
    profile = get_profile(yacht_id)
    return profile.get("scenes", [])


def get_hardware_for_yacht(yacht_id: str) -> Dict[str, Any]:
    """
    Helper if you need bus / Modbus config elsewhere.
    """
    profile = get_profile(yacht_id)
    return profile.get("hardware", {})


# -------------------------------------------------------------------
# New helpers used by app/routers/yachts.py
# -------------------------------------------------------------------

def list_known_yachts() -> List[Dict[str, str]]:
    """
    Return a simple list of all yachts the backend knows about.
    Each item is {id, name} so the UI can build a boat selector.
    """
    yachts: List[Dict[str, str]] = []
    for profile in PROFILES.values():
        yacht_meta = profile.get("yacht", {})
        yacht_id = yacht_meta.get("id", "unknown")
        name = yacht_meta.get("name", yacht_id)
        yachts.append(
            {
                "id": yacht_id,
                "name": name,
            }
        )
    return yachts


def get_yacht_meta(yacht_id: str) -> Dict[str, str]:
    """
    Return minimal metadata about a single yacht:
    {id, name}. Used by /yachts/{yacht_id}/meta.
    """
    profile = get_profile(yacht_id)
    yacht_meta = profile.get("yacht", {})
    return {
        "id": yacht_meta.get("id", yacht_id),
        "name": yacht_meta.get("name", yacht_id),
    }
