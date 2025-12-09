# app/yacht_profiles/__init__.py

from .default_cabin_cruiser_20_25ft import (
    PROFILE_ID as DEFAULT_CABIN_CRUISER_PROFILE_ID,
    get_devices_for_profile as _get_default_profile_devices,
)

# 1) Registry of which physical yacht uses which profile
YACHT_REGISTRY = {
    # id           # display name           # profile_id
    "marex-21-001": {
        "name": "Marex Flexi 21",
        "profile_id": DEFAULT_CABIN_CRUISER_PROFILE_ID,
    },
    # Later:
    # "sealine-25-001": {
    #     "name": "Sealine 25",
    #     "profile_id": DEFAULT_CABIN_CRUISER_PROFILE_ID,
    # },
}

# 2) Profile lookup
def get_profile_for_yacht(yacht_id: str) -> str:
    if yacht_id not in YACHT_REGISTRY:
        raise KeyError(f"Unknown yacht_id={yacht_id!r}")
    return YACHT_REGISTRY[yacht_id]["profile_id"]


def get_yacht_meta(yacht_id: str) -> dict:
    """
    Returns {id, name, profile_id} for one yacht,
    or raises KeyError if unknown.
    """
    cfg = YACHT_REGISTRY[yacht_id]
    return {
        "id": yacht_id,
        "name": cfg["name"],
        "profile_id": cfg["profile_id"],
    }


def list_yachts() -> list[dict]:
    """
    Returns a list of {id, name, profile_id} for the UI yacht selector.
    """
    return [get_yacht_meta(yid) for yid in YACHT_REGISTRY.keys()]


def get_devices_for_yacht(yacht_id: str) -> list[dict]:
    """
    Main entry point the rest of the backend should use.
    It decides which profile to load and returns the devices.
    """
    profile_id = get_profile_for_yacht(yacht_id)

    if profile_id == DEFAULT_CABIN_CRUISER_PROFILE_ID:
        return _get_default_profile_devices(profile_id)

    # If you add more profiles later:
    # elif profile_id == SOME_OTHER_PROFILE_ID: ...
    else:
        raise ValueError(f"Unsupported profile_id={profile_id!r}")
