# app/yacht_profiles/__init__.py

from typing import Dict, Any, List

from .default_cabin_cruiser_20_25ft import DEFAULT_CABIN_CRUISER_20_25FT

# All known yacht profiles go here.
# Keyed by yacht ID.
PROFILES: Dict[str, Dict[str, Any]] = {
    DEFAULT_CABIN_CRUISER_20_25FT["yacht"]["id"]: DEFAULT_CABIN_CRUISER_20_25FT,
}

DEFAULT_YACHT_ID: str = DEFAULT_CABIN_CRUISER_20_25FT["yacht"]["id"]


def get_profile(yacht_id: str) -> Dict[str, Any]:
    """
    Return the profile for the given yacht_id, falling back to the default profile
    if the ID is unknown.
    """
    return PROFILES.get(yacht_id, DEFAULT_CABIN_CRUISER_20_25FT)


def get_devices_for_yacht(yacht_id: str) -> List[Dict[str, Any]]:
    """
    Helper used by routers to retrieve the device list for a yacht.
    """
    profile = get_profile(yacht_id)
    return profile.get("devices", [])


def get_scenes_for_yacht(yacht_id: str) -> List[Dict[str, Any]]:
    """
    Helper for scenes router (if/when you wire it up).
    """
    profile = get_profile(yacht_id)
    return profile.get("scenes", [])


def get_hardware_for_yacht(yacht_id: str) -> Dict[str, Any]:
    """
    Helper if you need bus / Modbus config elsewhere.
    """
    profile = get_profile(yacht_id)
    return profile.get("hardware", {})
