import json
from typing import Any, Dict

from app.db import get_connection
from app.yacht_profiles import iter_known_profiles


def provision_yacht_from_file(path: str):
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    provision_yacht(cfg)


def provision_yacht(cfg: Dict[str, Any]):
    yacht = cfg["yacht"]
    devices = cfg.get("devices", [])
    scenes = cfg.get("scenes", [])
    hardware = cfg.get("hardware", {})

    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO yachts (id, name, hardware_json) VALUES (?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET name = excluded.name, hardware_json = excluded.hardware_json",
            (yacht["id"], yacht["name"], json.dumps(hardware)),
        )

        conn.execute("DELETE FROM devices WHERE yacht_id = ?", (yacht["id"],))
        conn.execute("DELETE FROM scenes WHERE yacht_id = ?", (yacht["id"],))
        conn.execute("DELETE FROM scene_actions WHERE yacht_id = ?", (yacht["id"],))

        for d in devices:
            conn.execute(
                "INSERT INTO devices "
                "(yacht_id, id, name, zone, type, state, hw_id, ai_control, "
                " max_runtime_seconds, requires_human_ack, control_authority) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    yacht["id"],
                    d["id"],
                    d["name"],
                    d["zone"],
                    d["type"],
                    json.dumps(d.get("state")),
                    d.get("hw_id"),
                    d.get("ai_control", "limited"),
                    d.get("max_runtime_seconds"),
                    1 if d.get("requires_human_ack", False) else 0,
                    _authority_from_ai_control(d.get("ai_control", "limited")),
                ),
            )

        for s in scenes:
            conn.execute(
                "INSERT INTO scenes (yacht_id, id, name, description) "
                "VALUES (?, ?, ?, ?)",
                (
                    yacht["id"],
                    s["id"],
                    s["name"],
                    s.get("description"),
                ),
            )
            for idx, action in enumerate(s.get("actions", [])):
                conn.execute(
                    "INSERT INTO scene_actions "
                    "(yacht_id, scene_id, order_index, device_id, state) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        yacht["id"],
                        s["id"],
                        idx,
                        action["device_id"],
                        json.dumps(action["state"]),
                    ),
                )

        conn.commit()
    finally:
        conn.close()


def seed_yacht_profile(cfg: Dict[str, Any]) -> None:
    """
    Add/update profile metadata without resetting existing device state.
    """
    yacht = cfg["yacht"]
    devices = cfg.get("devices", [])
    scenes = cfg.get("scenes", [])
    hardware = cfg.get("hardware", {})

    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO yachts (id, name, hardware_json) VALUES (?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET "
            "name = excluded.name, hardware_json = excluded.hardware_json",
            (yacht["id"], yacht["name"], json.dumps(hardware)),
        )

        for d in devices:
            authority = _authority_from_ai_control(d.get("ai_control", "limited"))
            existing = conn.execute(
                "SELECT state FROM devices WHERE yacht_id = ? AND id = ?",
                (yacht["id"], d["id"]),
            ).fetchone()

            if existing:
                conn.execute(
                    "UPDATE devices SET "
                    "name = ?, zone = ?, type = ?, hw_id = ?, ai_control = ?, "
                    "max_runtime_seconds = ?, requires_human_ack = ?, "
                    "control_authority = CASE "
                    "WHEN control_reason IS NULL THEN ? ELSE control_authority END "
                    "WHERE yacht_id = ? AND id = ?",
                    (
                        d["name"],
                        d["zone"],
                        d["type"],
                        d.get("hw_id"),
                        d.get("ai_control", "limited"),
                        d.get("max_runtime_seconds"),
                        1 if d.get("requires_human_ack", False) else 0,
                        authority,
                        yacht["id"],
                        d["id"],
                    ),
                )
            else:
                conn.execute(
                    "INSERT INTO devices "
                    "(yacht_id, id, name, zone, type, state, hw_id, ai_control, "
                    " max_runtime_seconds, requires_human_ack, control_authority) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        yacht["id"],
                        d["id"],
                        d["name"],
                        d["zone"],
                        d["type"],
                        json.dumps(d.get("state")),
                        d.get("hw_id"),
                        d.get("ai_control", "limited"),
                        d.get("max_runtime_seconds"),
                        1 if d.get("requires_human_ack", False) else 0,
                        authority,
                    ),
                )

        for s in scenes:
            conn.execute(
                "INSERT INTO scenes (yacht_id, id, name, description) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(yacht_id, id) DO UPDATE SET "
                "name = excluded.name, description = excluded.description",
                (
                    yacht["id"],
                    s["id"],
                    s["name"],
                    s.get("description"),
                ),
            )
            conn.execute(
                "DELETE FROM scene_actions WHERE yacht_id = ? AND scene_id = ?",
                (yacht["id"], s["id"]),
            )
            for idx, action in enumerate(s.get("actions", [])):
                conn.execute(
                    "INSERT INTO scene_actions "
                    "(yacht_id, scene_id, order_index, device_id, state) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        yacht["id"],
                        s["id"],
                        idx,
                        action["device_id"],
                        json.dumps(action["state"]),
                    ),
                )

        conn.commit()
    finally:
        conn.close()


def seed_known_yacht_profiles() -> None:
    for profile in iter_known_profiles():
        seed_yacht_profile(profile)


def _authority_from_ai_control(ai_control: str) -> str:
    if ai_control == "allowed":
        return "ai_allowed"
    if ai_control == "limited":
        return "ai_suggest_only"
    return "manual"
