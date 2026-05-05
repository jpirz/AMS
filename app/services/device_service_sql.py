import json
from datetime import datetime, timezone
from typing import List, Any

from app.db import get_connection
from app.models import Device, DeviceType
from app.services.event_service_sql import EventLogger
from app.hardware.manager import HardwareManager


class DeviceService:
    def __init__(self, hw_manager: HardwareManager, event_logger: EventLogger):
        self.hw_manager = hw_manager
        self.events = event_logger

    def list_devices(self, yacht_id: str) -> List[Device]:
        conn = get_connection()
        try:
            cur = conn.execute(
                "SELECT yacht_id, id, name, zone, type, state, hw_id, "
                "ai_control, max_runtime_seconds, requires_human_ack, "
                "control_authority, control_reason, last_changed_at, "
                "last_changed_by, current_on_since, total_runtime_seconds "
                "FROM devices WHERE yacht_id = ?",
                (yacht_id,),
            )
            rows = cur.fetchall()
        finally:
            conn.close()

        devices: List[Device] = []
        for r in rows:
            state = json.loads(r["state"]) if r["state"] is not None else None
            devices.append(
                Device(
                    yacht_id=r["yacht_id"],
                    id=r["id"],
                    name=r["name"],
                    zone=r["zone"],
                    type=DeviceType(r["type"]),
                    state=state,
                    hw_id=r["hw_id"],
                    ai_control=r["ai_control"],
                    max_runtime_seconds=r["max_runtime_seconds"],
                    requires_human_ack=bool(r["requires_human_ack"]),
                    control_authority=r["control_authority"],
                    control_reason=r["control_reason"],
                    last_changed_at=_parse_dt(r["last_changed_at"]),
                    last_changed_by=r["last_changed_by"],
                    current_on_since=_parse_dt(r["current_on_since"]),
                    total_runtime_seconds=r["total_runtime_seconds"] or 0,
                )
            )
        return devices

    def get_device(self, yacht_id: str, device_id: str) -> Device:
        conn = get_connection()
        try:
            cur = conn.execute(
                "SELECT yacht_id, id, name, zone, type, state, hw_id, "
                "ai_control, max_runtime_seconds, requires_human_ack, "
                "control_authority, control_reason, last_changed_at, "
                "last_changed_by, current_on_since, total_runtime_seconds "
                "FROM devices WHERE yacht_id = ? AND id = ?",
                (yacht_id, device_id),
            )
            row = cur.fetchone()
        finally:
            conn.close()

        if row is None:
            raise KeyError(device_id)

        state = json.loads(row["state"]) if row["state"] is not None else None
        return Device(
            yacht_id=row["yacht_id"],
            id=row["id"],
            name=row["name"],
            zone=row["zone"],
            type=DeviceType(row["type"]),
            state=state,
            hw_id=row["hw_id"],
            ai_control=row["ai_control"],
            max_runtime_seconds=row["max_runtime_seconds"],
            requires_human_ack=bool(row["requires_human_ack"]),
            control_authority=row["control_authority"],
            control_reason=row["control_reason"],
            last_changed_at=_parse_dt(row["last_changed_at"]),
            last_changed_by=row["last_changed_by"],
            current_on_since=_parse_dt(row["current_on_since"]),
            total_runtime_seconds=row["total_runtime_seconds"] or 0,
        )

    def set_device_state(self, yacht_id: str, source: str, device_id: str, state: Any) -> Device:
        device = self.get_device(yacht_id, device_id)
        previous_state = device.state

        if device.type != DeviceType.SENSOR and not isinstance(state, bool):
            raise ValueError("Non-sensor devices expect boolean state")

        if device.type != DeviceType.SENSOR and device.hw_id and isinstance(state, bool):
            hw = self.hw_manager.get_io(yacht_id)
            hw.set_output(device.hw_id, state)

        now = datetime.now(timezone.utc)
        last_changed_at = device.last_changed_at
        last_changed_by = device.last_changed_by
        current_on_since = device.current_on_since
        total_runtime_seconds = device.total_runtime_seconds

        if previous_state != state:
            last_changed_at = now
            last_changed_by = source

            if device.type != DeviceType.SENSOR:
                if previous_state is True and current_on_since is not None:
                    total_runtime_seconds += max(
                        0,
                        int((now - current_on_since).total_seconds()),
                    )
                    current_on_since = None
                if state is True and current_on_since is None:
                    current_on_since = now
                if state is False:
                    current_on_since = None

        conn = get_connection()
        try:
            conn.execute(
                "UPDATE devices SET state = ?, last_changed_at = ?, "
                "last_changed_by = ?, current_on_since = ?, "
                "total_runtime_seconds = ? WHERE yacht_id = ? AND id = ?",
                (
                    json.dumps(state),
                    _dt_str(last_changed_at),
                    last_changed_by,
                    _dt_str(current_on_since),
                    total_runtime_seconds,
                    yacht_id,
                    device_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        device.state = state
        device.last_changed_at = last_changed_at
        device.last_changed_by = last_changed_by
        device.current_on_since = current_on_since
        device.total_runtime_seconds = total_runtime_seconds

        self.events.log(
            yacht_id=yacht_id,
            source=source,
            type="device_change",
            details={"device_id": device_id, "new_state": state},
        )

        return device

    def set_control_authority(
        self,
        yacht_id: str,
        source: str,
        device_id: str,
        authority: str,
        reason: str | None = None,
    ) -> Device:
        if authority not in {"manual", "ai_allowed", "ai_suggest_only", "locked_out"}:
            raise ValueError("Invalid control authority")

        self.get_device(yacht_id, device_id)
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE devices SET control_authority = ?, control_reason = ? "
                "WHERE yacht_id = ? AND id = ?",
                (authority, reason, yacht_id, device_id),
            )
            conn.commit()
        finally:
            conn.close()

        self.events.log(
            yacht_id=yacht_id,
            source=source,
            type="control_authority_change",
            details={"device_id": device_id, "authority": authority, "reason": reason},
        )
        return self.get_device(yacht_id, device_id)


def _parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _dt_str(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
