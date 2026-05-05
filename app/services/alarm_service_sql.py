import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.db import get_connection
from app.models import Device, Event
from app.services.device_service_sql import DeviceService
from app.services.event_service_sql import EventLogger


EXPLICIT_ALARM_IDS = {
    "bilge_float_high",
    "battery_low_alarm",
    "smoke_cabin",
}


class AlarmService:
    def __init__(self, device_service: DeviceService, event_logger: EventLogger):
        self.devices = device_service
        self.events = event_logger

    def active_alarms(self, yacht_id: str) -> List[Dict[str, Any]]:
        self.sync_all(yacht_id)
        return self._list_rows(yacht_id, status="active")

    def alarm_history(self, yacht_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        self.sync_all(yacht_id)
        return self._list_rows(yacht_id, limit=limit)

    def acknowledge_active(self, yacht_id: str, source: str = "user_ui") -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        conn = get_connection()
        try:
            cur = conn.execute(
                "UPDATE alarms SET acknowledged_at = ? "
                "WHERE yacht_id = ? AND status = 'active' AND acknowledged_at IS NULL",
                (now, yacht_id),
            )
            conn.commit()
            count = cur.rowcount
        finally:
            conn.close()

        self.events.log(
            yacht_id=yacht_id,
            source=source,
            type="alarms_acknowledged",
            details={"count": count},
        )
        return {"status": "ok", "acknowledged": count}

    def clear_cleared(self, yacht_id: str, source: str = "user_ui") -> Dict[str, Any]:
        conn = get_connection()
        try:
            cur = conn.execute(
                "DELETE FROM alarms WHERE yacht_id = ? AND status = 'cleared'",
                (yacht_id,),
            )
            conn.commit()
            count = cur.rowcount
        finally:
            conn.close()

        self.events.log(
            yacht_id=yacht_id,
            source=source,
            type="cleared_alarm_history_removed",
            details={"count": count},
        )
        return {"status": "ok", "cleared": count}

    def sync_all(self, yacht_id: str) -> None:
        for device in self.devices.list_devices(yacht_id):
            self.sync_device(yacht_id, device.id, device=device)

    def sync_device(self, yacht_id: str, device_id: str, device: Device | None = None) -> None:
        device = device or self.devices.get_device(yacht_id, device_id)
        if not self.is_alarmish(device):
            return

        if self.is_alarm_state(device, device.state):
            self._raise_or_update_alarm(yacht_id, device)
        else:
            self._clear_alarm(yacht_id, device)

    def _event_to_alarm_record(
        self,
        event: Event,
        device_map: Dict[str, Device],
    ) -> Optional[Dict[str, Any]]:
        if event.type != "device_change":
            return None

        device_id = event.details.get("device_id")
        if not device_id:
            return None

        device = device_map.get(device_id)
        if device is None or not self.is_alarmish(device):
            return None

        state = event.details.get("new_state")
        alarm_type = "ALARM" if self.is_alarm_state(device, state) else "ALARM_CLEAR"
        return self._alarm_record(device, alarm_type, event.timestamp.isoformat(), state)

    def _alarm_record(
        self,
        device: Device,
        alarm_type: str,
        timestamp: str,
        state: Any = None,
    ) -> Dict[str, Any]:
        value = device.state if state is None else state
        return {
            "timestamp": timestamp,
            "type": alarm_type,
            "source": "alarm_service",
            "device_id": device.id,
            "name": device.name,
            "zone": device.zone,
            "severity": self._severity(device),
            "state": value,
            "details": {
                "device_id": device.id,
                "name": device.name,
                "zone": device.zone,
                "state": value,
            },
        }

    def _raise_or_update_alarm(self, yacht_id: str, device: Device) -> None:
        now = datetime.now(timezone.utc).isoformat()
        alarm_key = f"device:{device.id}"
        details = self._alarm_record(device, "ALARM", now)
        conn = get_connection()
        try:
            existing = conn.execute(
                "SELECT id FROM alarms WHERE yacht_id = ? AND alarm_key = ? AND status = 'active'",
                (yacht_id, alarm_key),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE alarms SET state = ?, last_changed_at = ?, details = ? "
                    "WHERE id = ?",
                    (json.dumps(device.state), now, json.dumps(details), existing["id"]),
                )
            else:
                conn.execute(
                    "INSERT INTO alarms "
                    "(yacht_id, alarm_key, device_id, name, zone, severity, status, "
                    "state, first_raised_at, last_changed_at, details) "
                    "VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?)",
                    (
                        yacht_id,
                        alarm_key,
                        device.id,
                        device.name,
                        device.zone,
                        self._severity(device),
                        json.dumps(device.state),
                        now,
                        now,
                        json.dumps(details),
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    def _clear_alarm(self, yacht_id: str, device: Device) -> None:
        now = datetime.now(timezone.utc).isoformat()
        alarm_key = f"device:{device.id}"
        details = self._alarm_record(device, "ALARM_CLEAR", now)
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE alarms SET status = 'cleared', state = ?, "
                "last_changed_at = ?, cleared_at = ?, details = ? "
                "WHERE yacht_id = ? AND alarm_key = ? AND status = 'active'",
                (
                    json.dumps(device.state),
                    now,
                    now,
                    json.dumps(details),
                    yacht_id,
                    alarm_key,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def _list_rows(
        self,
        yacht_id: str,
        status: str | None = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        query = (
            "SELECT id, alarm_key, device_id, name, zone, severity, status, state, "
            "first_raised_at, last_changed_at, acknowledged_at, cleared_at, details "
            "FROM alarms WHERE yacht_id = ?"
        )
        params: list[Any] = [yacht_id]
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY last_changed_at DESC LIMIT ?"
        params.append(limit)

        conn = get_connection()
        try:
            rows = conn.execute(query, params).fetchall()
        finally:
            conn.close()

        out: List[Dict[str, Any]] = []
        for row in rows:
            details = json.loads(row["details"])
            out.append(
                {
                    "id": row["id"],
                    "alarm_key": row["alarm_key"],
                    "device_id": row["device_id"],
                    "name": row["name"],
                    "zone": row["zone"],
                    "severity": row["severity"],
                    "status": row["status"],
                    "state": json.loads(row["state"]) if row["state"] is not None else None,
                    "timestamp": row["last_changed_at"],
                    "type": "ALARM" if row["status"] == "active" else "ALARM_CLEAR",
                    "source": "alarm_service",
                    "first_raised_at": row["first_raised_at"],
                    "last_changed_at": row["last_changed_at"],
                    "acknowledged_at": row["acknowledged_at"],
                    "cleared_at": row["cleared_at"],
                    "details": details.get("details", details),
                }
            )
        return out

    @staticmethod
    def is_alarmish(device: Device) -> bool:
        haystack = f"{device.id} {device.name}".lower()

        if device.id in EXPLICIT_ALARM_IDS:
            return True

        if device.type.value == "pump" and "bilge" in haystack:
            return True

        keywords = [
            "bilge",
            "battery",
            "fuel",
            "tank",
            "temp",
            "temperature",
            "overheat",
            "shore",
            "ac_input",
            "smoke",
            "fire",
            "co2",
            "leak",
            "water",
        ]
        return any(keyword in haystack for keyword in keywords)

    @staticmethod
    def is_alarm_state(device: Device, value: Any) -> bool:
        haystack = f"{device.id} {device.name}".lower()

        if device.id in EXPLICIT_ALARM_IDS and value is True:
            return True

        if device.type.value == "pump" and "bilge" in haystack and value is True:
            return True

        if isinstance(value, bool):
            if "shore" in haystack or "ac_input" in haystack:
                return value is False

            bool_keywords = ["bilge", "battery", "alarm", "fault", "smoke", "fire", "leak"]
            return value is True and any(keyword in haystack for keyword in bool_keywords)

        if isinstance(value, (int, float)):
            if "fuel" in haystack or "tank" in haystack:
                return value <= 20 or value >= 95

            if "battery" in haystack and "volt" in haystack:
                return value < 11.5

            if "temp" in haystack or "temperature" in haystack:
                return value > 90

        return False

    @staticmethod
    def _severity(device: Device) -> str:
        haystack = f"{device.id} {device.name}".lower()
        if any(keyword in haystack for keyword in ["bilge", "smoke", "fire", "leak", "co2"]):
            return "critical"
        if any(keyword in haystack for keyword in ["battery", "fuel", "tank", "temp", "shore"]):
            return "warning"
        return "info"
