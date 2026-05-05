from datetime import datetime, timezone
from typing import Any, Dict, List

from app.models import Device
from app.services.alarm_service_sql import AlarmService
from app.services.device_service_sql import DeviceService
from app.services.event_service_sql import EventLogger
from app.services.vessel_state_sql import VesselStateService


class SafetyService:
    def __init__(
        self,
        device_service: DeviceService,
        alarm_service: AlarmService,
        vessel_state: VesselStateService,
        event_logger: EventLogger,
    ):
        self.devices = device_service
        self.alarms = alarm_service
        self.vessel_state = vessel_state
        self.events = event_logger

    def enforce(self, yacht_id: str, source: str = "safety_rules") -> Dict[str, Any]:
        devices = {d.id: d for d in self.devices.list_devices(yacht_id)}
        mode = self.vessel_state.get_mode(yacht_id)
        actions: List[Dict[str, Any]] = []

        actions.extend(self._enforce_navigation_lights(yacht_id, mode, devices))
        actions.extend(self._enforce_bilge(yacht_id, devices))
        actions.extend(self._enforce_battery_and_shore(yacht_id, mode, devices))
        actions.extend(self._enforce_smoke(yacht_id, devices))

        self.alarms.sync_all(yacht_id)
        if actions:
            self.events.log(
                yacht_id=yacht_id,
                source=source,
                type="safety_rules_applied",
                details={"mode": mode, "actions": actions},
            )
        return {"yacht_id": yacht_id, "mode": mode, "actions": actions}

    def _enforce_navigation_lights(
        self,
        yacht_id: str,
        mode: str,
        devices: Dict[str, Device],
    ) -> List[Dict[str, Any]]:
        actions: List[Dict[str, Any]] = []
        if mode == "at_anchor":
            actions.extend(
                [
                    self._set_if_needed(yacht_id, devices, "anchor_light", True, "Anchor mode requires anchor light on."),
                    self._set_if_needed(yacht_id, devices, "nav_lights", False, "Anchor mode requires navigation lights off."),
                ]
            )
        elif mode == "underway":
            actions.extend(
                [
                    self._set_if_needed(yacht_id, devices, "nav_lights", True, "Underway mode requires navigation lights on."),
                    self._set_if_needed(yacht_id, devices, "anchor_light", False, "Underway mode requires anchor light off."),
                ]
            )
        return [a for a in actions if a]

    def _enforce_bilge(self, yacht_id: str, devices: Dict[str, Device]) -> List[Dict[str, Any]]:
        actions: List[Dict[str, Any]] = []
        high = devices.get("bilge_float_high")
        override = devices.get("bilge_pump_auto_override")
        if high and high.state is True:
            action = self._set_if_needed(
                yacht_id,
                devices,
                "bilge_pump_auto_override",
                True,
                "Bilge high float active; enabling pump override.",
            )
            if action:
                actions.append(action)

        if override and override.state is True and override.current_on_since:
            max_runtime = override.max_runtime_seconds or 600
            elapsed = (datetime.now(timezone.utc) - override.current_on_since).total_seconds()
            if elapsed > max_runtime:
                action = self._set_if_needed(
                    yacht_id,
                    devices,
                    "bilge_pump_auto_override",
                    False,
                    "Pump runtime limit exceeded; disabling override for protection.",
                )
                if action:
                    actions.append(action)
        return actions

    def _enforce_battery_and_shore(
        self,
        yacht_id: str,
        mode: str,
        devices: Dict[str, Device],
    ) -> List[Dict[str, Any]]:
        actions: List[Dict[str, Any]] = []
        house = devices.get("battery_voltage_house")
        shore = devices.get("shore_power_present")
        low_house = isinstance(house.state if house else None, (int, float)) and house.state < 11.5
        no_shore_unattended = shore is not None and shore.state is False and mode == "unattended"

        if low_house or no_shore_unattended:
            reason = "Low battery or unattended shore power loss; shedding non-essential loads."
            for device_id in ["inverter_power", "cabin_fan", "cabin_heater", "fridge"]:
                action = self._set_if_needed(yacht_id, devices, device_id, False, reason)
                if action:
                    actions.append(action)
        return actions

    def _enforce_smoke(self, yacht_id: str, devices: Dict[str, Device]) -> List[Dict[str, Any]]:
        smoke = devices.get("smoke_cabin")
        if smoke and smoke.state is True:
            action = self._set_if_needed(
                yacht_id,
                devices,
                "cabin_heater",
                False,
                "Cabin smoke alarm active; disabling cabin heater.",
            )
            return [action] if action else []
        return []

    def _set_if_needed(
        self,
        yacht_id: str,
        devices: Dict[str, Device],
        device_id: str,
        target_state: bool,
        reason: str,
    ) -> Dict[str, Any] | None:
        device = devices.get(device_id)
        if device is None or device.state is target_state:
            return None

        updated = self.devices.set_device_state(
            yacht_id=yacht_id,
            source="safety_rules",
            device_id=device_id,
            state=target_state,
        )
        devices[device_id] = updated
        self.alarms.sync_device(yacht_id, device_id)
        return {"device_id": device_id, "state": target_state, "reason": reason}
