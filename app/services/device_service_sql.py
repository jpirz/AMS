import json
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
                "ai_control, max_runtime_seconds, requires_human_ack "
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
                )
            )
        return devices

    def get_device(self, yacht_id: str, device_id: str) -> Device:
        conn = get_connection()
        try:
            cur = conn.execute(
                "SELECT yacht_id, id, name, zone, type, state, hw_id, "
                "ai_control, max_runtime_seconds, requires_human_ack "
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
        )

    def set_device_state(self, yacht_id: str, source: str, device_id: str, state: Any) -> Device:
        device = self.get_device(yacht_id, device_id)

        if device.type != DeviceType.SENSOR and not isinstance(state, bool):
            raise ValueError("Non-sensor devices expect boolean state")

        if device.hw_id and isinstance(state, bool):
            hw = self.hw_manager.get_io(yacht_id)
            hw.set_output(device.hw_id, state)

        conn = get_connection()
        try:
            conn.execute(
                "UPDATE devices SET state = ? WHERE yacht_id = ? AND id = ?",
                (json.dumps(state), yacht_id, device_id),
            )
            conn.commit()
        finally:
            conn.close()

        device.state = state

        self.events.log(
            yacht_id=yacht_id,
            source=source,
            type="device_change",
            details={"device_id": device_id, "new_state": state},
        )

        return device
