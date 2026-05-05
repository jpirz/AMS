from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.models import Device, DeviceType
from app.services.ai_state_sql import AIStateService
from app.services.alarm_service_sql import AlarmService
from app.services.device_service_sql import DeviceService
from app.services.event_service_sql import EventLogger
from app.services.vessel_state_sql import VesselStateService


class AIInsightsService:
    def __init__(
        self,
        device_service: DeviceService,
        alarm_service: AlarmService,
        event_logger: EventLogger,
        vessel_state: VesselStateService,
        ai_state: AIStateService,
    ):
        self.devices = device_service
        self.alarms = alarm_service
        self.events = event_logger
        self.vessel_state = vessel_state
        self.ai_state = ai_state

    def status_summary(self, yacht_id: str) -> Dict[str, Any]:
        devices = self.devices.list_devices(yacht_id)
        by_id = {d.id: d for d in devices}
        active_alarms = self.alarms.active_alarms(yacht_id)
        mode = self.vessel_state.get_mode(yacht_id)
        occupancy = self.ai_state.get_occupancy(yacht_id)
        suggestions = self.build_suggestions(yacht_id, devices=devices, active_alarms=active_alarms, mode=mode)
        maintenance = self.maintenance_intelligence(yacht_id, devices=devices)
        recent_events = self.events.list_events(yacht_id, limit=10)

        risk_items = self._risk_items(by_id, active_alarms, mode)
        risk_level = self._risk_level(active_alarms, risk_items, maintenance["alerts"])
        critical_count = sum(1 for alarm in active_alarms if alarm.get("severity") == "critical")

        if active_alarms:
            headline = f"{len(active_alarms)} active alarm(s); {critical_count} critical."
        elif maintenance["alerts"]:
            headline = f"No active alarms; {len(maintenance['alerts'])} maintenance item(s) need attention."
        else:
            headline = "No active alarms. Core systems look nominal."

        return {
            "yacht_id": yacht_id,
            "generated_at": _now_iso(),
            "mode": mode,
            "occupancy": occupancy,
            "risk_level": risk_level,
            "headline": headline,
            "active_alarm_count": len(active_alarms),
            "critical_alarm_count": critical_count,
            "active_alarms": active_alarms,
            "risk_items": risk_items,
            "recommended_actions": suggestions[:5],
            "maintenance_alerts": maintenance["alerts"][:5],
            "recent_events": [e.model_dump(mode="json") for e in recent_events],
        }

    def build_suggestions(
        self,
        yacht_id: str,
        devices: List[Device] | None = None,
        active_alarms: List[Dict[str, Any]] | None = None,
        mode: str | None = None,
    ) -> List[Dict[str, Any]]:
        devices = devices or self.devices.list_devices(yacht_id)
        active_alarms = active_alarms if active_alarms is not None else self.alarms.active_alarms(yacht_id)
        mode = mode or self.vessel_state.get_mode(yacht_id)
        by_id = {d.id: d for d in devices}
        suggestions: List[Dict[str, Any]] = []

        def add_device_action(
            suggestion_id: str,
            title: str,
            reason: str,
            device_id: str,
            target_state: bool,
            severity: str,
            confidence: float,
            category: str,
            impact: str,
        ) -> None:
            device = by_id.get(device_id)
            if device is None or device.state is target_state:
                return

            approveable = device.type != DeviceType.SENSOR and device.control_authority != "locked_out"
            suggestions.append(
                {
                    "id": suggestion_id,
                    "title": title,
                    "reason": reason,
                    "category": category,
                    "severity": severity,
                    "priority": _severity_to_priority(severity),
                    "confidence": confidence,
                    "rank": _rank(severity, confidence),
                    "approveable": approveable,
                    "impact": impact,
                    "created_at": _now_iso(),
                    "action": {
                        "action_id": suggestion_id,
                        "type": "set_device_state",
                        "device_id": device_id,
                        "target_state": target_state,
                        "priority": _severity_to_priority(severity),
                        "reason": reason,
                    }
                    if approveable
                    else None,
                }
            )

        def add_advisory(
            suggestion_id: str,
            title: str,
            reason: str,
            severity: str,
            confidence: float,
            category: str,
            impact: str,
        ) -> None:
            suggestions.append(
                {
                    "id": suggestion_id,
                    "title": title,
                    "reason": reason,
                    "category": category,
                    "severity": severity,
                    "priority": _severity_to_priority(severity),
                    "confidence": confidence,
                    "rank": _rank(severity, confidence),
                    "approveable": False,
                    "impact": impact,
                    "created_at": _now_iso(),
                    "action": None,
                }
            )

        alarm_ids = {a.get("device_id") for a in active_alarms}

        if "bilge_float_high" in alarm_ids or _state_is(by_id, "bilge_float_high", True):
            add_device_action(
                "suggest-bilge-pump",
                "Enable bilge pump override",
                "Bilge high float is active.",
                "bilge_pump_auto_override",
                True,
                "critical",
                0.96,
                "safety",
                "Starts automatic bilge pumping until the alarm clears or runtime protection intervenes.",
            )

        if "smoke_cabin" in alarm_ids or _state_is(by_id, "smoke_cabin", True):
            add_device_action(
                "suggest-disable-heater-smoke",
                "Disable cabin heater",
                "Cabin smoke detector is active.",
                "cabin_heater",
                False,
                "critical",
                0.95,
                "safety",
                "Removes a likely heat source while the smoke alarm is investigated.",
            )
            add_advisory(
                "suggest-check-smoke-source",
                "Inspect cabin smoke source",
                "Smoke alarms require physical verification before reset.",
                "critical",
                0.92,
                "incident",
                "No device action can verify smoke. Check cabin and engine spaces.",
            )

        house = by_id.get("battery_voltage_house")
        battery_low = "battery_low_alarm" in alarm_ids or (
            house is not None and isinstance(house.state, (int, float)) and house.state < 11.8
        )
        if battery_low:
            for device_id in ["inverter_power", "cabin_heater", "cabin_fan", "fridge"]:
                add_device_action(
                    f"suggest-shed-{device_id}",
                    f"Shed {device_id.replace('_', ' ')}",
                    "House battery is low; shed non-essential loads.",
                    device_id,
                    False,
                    "warning",
                    0.88,
                    "energy",
                    "Reduces house battery draw.",
                )

        shore = by_id.get("shore_power_present")
        if shore and shore.state is False and mode == "unattended":
            add_advisory(
                "suggest-check-shore-power",
                "Check shore power connection",
                "Boat is unattended and shore power is not present.",
                "warning",
                0.9,
                "energy",
                "Inspect pedestal, cable, breaker, and charger state.",
            )

        fuel = by_id.get("fuel_tank_level")
        if fuel and isinstance(fuel.state, (int, float)) and fuel.state <= 20:
            add_advisory(
                "suggest-low-fuel",
                "Plan refuel",
                "Fuel tank level is low.",
                "warning",
                0.82,
                "maintenance",
                "Avoid relying on long engine runtime until refueled.",
            )

        temp = by_id.get("engine_room_temp")
        if temp and isinstance(temp.state, (int, float)) and temp.state > 90:
            add_advisory(
                "suggest-engine-temp-check",
                "Inspect engine room temperature",
                "Engine room temperature is above safe threshold.",
                "critical",
                0.9,
                "safety",
                "Check ventilation, cooling, and heat sources.",
            )

        if mode == "at_anchor":
            add_device_action(
                "suggest-anchor-light",
                "Turn on anchor light",
                "At-anchor mode expects anchor light.",
                "anchor_light",
                True,
                "warning",
                0.93,
                "navigation",
                "Shows correct vessel status while anchored.",
            )
            add_device_action(
                "suggest-nav-off",
                "Turn off navigation lights",
                "At-anchor mode expects navigation lights off.",
                "nav_lights",
                False,
                "warning",
                0.9,
                "navigation",
                "Avoids showing the wrong navigation signal.",
            )
        elif mode == "underway":
            add_device_action(
                "suggest-nav-on",
                "Turn on navigation lights",
                "Underway mode expects navigation lights.",
                "nav_lights",
                True,
                "warning",
                0.93,
                "navigation",
                "Shows correct vessel status while underway.",
            )
            add_device_action(
                "suggest-anchor-off",
                "Turn off anchor light",
                "Underway mode expects anchor light off.",
                "anchor_light",
                False,
                "warning",
                0.9,
                "navigation",
                "Avoids showing the wrong navigation signal.",
            )

        for alert in self.maintenance_intelligence(yacht_id, devices=devices)["alerts"]:
            add_advisory(
                f"suggest-maint-{alert['id']}",
                alert["title"],
                alert["reason"],
                alert["severity"],
                0.76,
                "maintenance",
                alert["recommended_action"],
            )

        deduped = {s["id"]: s for s in suggestions}
        return sorted(deduped.values(), key=lambda s: (-s["rank"], s["id"]))

    def safety_explanations(self, yacht_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        explanations: List[Dict[str, Any]] = []
        for event in self.events.list_events(yacht_id, limit=200):
            if event.type != "safety_rules_applied":
                continue
            for action in event.details.get("actions", []):
                explanations.append(
                    {
                        "timestamp": event.timestamp.isoformat(),
                        "source": event.source,
                        "device_id": action.get("device_id"),
                        "state": action.get("state"),
                        "reason": action.get("reason"),
                        "mode": event.details.get("mode"),
                    }
                )
                if len(explanations) >= limit:
                    return explanations
        return explanations

    def incident_reports(self, yacht_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        reports: List[Dict[str, Any]] = []
        safety_actions = self.safety_explanations(yacht_id, limit=100)

        for alarm in self.alarms.alarm_history(yacht_id, limit=limit):
            related_actions = [
                action for action in safety_actions if action.get("device_id") == alarm.get("device_id")
            ]
            reports.append(
                {
                    "id": f"alarm-{alarm['id']}",
                    "title": f"{alarm['name']} {alarm['status']}",
                    "status": alarm["status"],
                    "severity": alarm["severity"],
                    "device_id": alarm["device_id"],
                    "started_at": alarm["first_raised_at"],
                    "last_changed_at": alarm["last_changed_at"],
                    "summary": self._incident_summary(alarm),
                    "likely_cause": self._likely_cause(alarm),
                    "recommended_checks": self._recommended_checks(alarm),
                    "related_safety_actions": related_actions[:5],
                }
            )
        return reports

    def maintenance_intelligence(
        self,
        yacht_id: str,
        devices: List[Device] | None = None,
    ) -> Dict[str, Any]:
        devices = devices or self.devices.list_devices(yacht_id)
        events = self.events.list_events(yacht_id, limit=500)
        alerts: List[Dict[str, Any]] = []

        for device in devices:
            runtime = _runtime_seconds(device)
            if device.max_runtime_seconds and device.state is True:
                ratio = runtime / max(device.max_runtime_seconds, 1)
                if ratio >= 1:
                    severity = "critical"
                    reason = f"{device.name} has exceeded its configured runtime limit."
                elif ratio >= 0.75:
                    severity = "warning"
                    reason = f"{device.name} is approaching its configured runtime limit."
                else:
                    continue
                alerts.append(
                    {
                        "id": f"runtime-{device.id}",
                        "device_id": device.id,
                        "title": f"Runtime watch: {device.name}",
                        "severity": severity,
                        "runtime_seconds": runtime,
                        "reason": reason,
                        "recommended_action": "Inspect the load and switch it off if it is not needed.",
                    }
                )

            if device.type == DeviceType.PUMP and runtime >= 600:
                alerts.append(
                    {
                        "id": f"pump-runtime-{device.id}",
                        "device_id": device.id,
                        "title": f"Pump usage high: {device.name}",
                        "severity": "warning",
                        "runtime_seconds": runtime,
                        "reason": f"{device.name} has accumulated {_format_duration(runtime)} runtime.",
                        "recommended_action": "Check for leaks, stuck switches, or abnormal demand.",
                    }
                )

        device_change_counts = Counter()
        for event in events:
            if event.type == "device_change":
                device_id = event.details.get("device_id")
                if device_id:
                    device_change_counts[device_id] += 1

        for device_id in ["bilge_pump_auto_override", "freshwater_pump", "battery_low_alarm"]:
            count = device_change_counts.get(device_id, 0)
            if count >= 4:
                alerts.append(
                    {
                        "id": f"repeat-{device_id}",
                        "device_id": device_id,
                        "title": f"Repeated changes: {device_id.replace('_', ' ')}",
                        "severity": "warning",
                        "change_count": count,
                        "reason": f"{device_id} changed {count} times in recent history.",
                        "recommended_action": "Inspect the system for cycling, nuisance alarms, or unstable sensors.",
                    }
                )

        house = next((d for d in devices if d.id == "battery_voltage_house"), None)
        if house and isinstance(house.state, (int, float)) and house.state < 12.0:
            alerts.append(
                {
                    "id": "battery-voltage-low",
                    "device_id": house.id,
                    "title": "House battery trending low",
                    "severity": "warning",
                    "voltage": house.state,
                    "reason": f"House battery is {house.state}V.",
                    "recommended_action": "Reduce loads and confirm charging source.",
                }
            )

        deduped = {alert["id"]: alert for alert in alerts}
        ordered = sorted(deduped.values(), key=lambda a: (_severity_sort(a["severity"]), a["id"]))
        return {
            "yacht_id": yacht_id,
            "generated_at": _now_iso(),
            "alerts": ordered,
        }

    def _risk_items(
        self,
        devices: Dict[str, Device],
        active_alarms: List[Dict[str, Any]],
        mode: str,
    ) -> List[Dict[str, Any]]:
        items = [
            {
                "id": f"alarm-{alarm['device_id']}",
                "severity": alarm["severity"],
                "title": alarm["name"],
                "reason": f"Alarm is active on {alarm['device_id']}.",
            }
            for alarm in active_alarms
        ]

        if mode == "underway" and not _state_is(devices, "nav_lights", True):
            items.append(
                {
                    "id": "risk-nav-lights-off",
                    "severity": "warning",
                    "title": "Navigation lights off",
                    "reason": "Underway mode expects navigation lights on.",
                }
            )
        if mode == "at_anchor" and not _state_is(devices, "anchor_light", True):
            items.append(
                {
                    "id": "risk-anchor-light-off",
                    "severity": "warning",
                    "title": "Anchor light off",
                    "reason": "At-anchor mode expects anchor light on.",
                }
            )
        return items

    def _risk_level(
        self,
        active_alarms: List[Dict[str, Any]],
        risk_items: List[Dict[str, Any]],
        maintenance_alerts: List[Dict[str, Any]],
    ) -> str:
        severities = [a.get("severity") for a in active_alarms + risk_items + maintenance_alerts]
        if "critical" in severities:
            return "critical"
        if "warning" in severities:
            return "warning"
        if severities:
            return "attention"
        return "nominal"

    def _incident_summary(self, alarm: Dict[str, Any]) -> str:
        state = alarm.get("state")
        if alarm["status"] == "active":
            return f"{alarm['name']} is active with state {state!r}."
        return f"{alarm['name']} cleared after reporting state {state!r}."

    def _likely_cause(self, alarm: Dict[str, Any]) -> str:
        haystack = f"{alarm.get('device_id')} {alarm.get('name')}".lower()
        if "bilge" in haystack:
            return "Water in bilge, float switch test, or stuck bilge sensor."
        if "battery" in haystack:
            return "High electrical load, charging loss, or low battery state of charge."
        if "shore" in haystack:
            return "Shore cable, pedestal breaker, charger, or marina supply issue."
        if "smoke" in haystack or "fire" in haystack:
            return "Smoke detector activation; treat as real until physically checked."
        if "fuel" in haystack:
            return "Low or abnormal tank level reading."
        if "temp" in haystack:
            return "Ventilation, cooling, or heat source issue."
        return "Sensor activation or abnormal equipment state."

    def _recommended_checks(self, alarm: Dict[str, Any]) -> List[str]:
        haystack = f"{alarm.get('device_id')} {alarm.get('name')}".lower()
        if "bilge" in haystack:
            return ["Check bilge water level.", "Verify pump outlet flow.", "Inspect float switch."]
        if "battery" in haystack:
            return ["Check charger and shore power.", "Shed non-essential loads.", "Inspect battery voltage."]
        if "shore" in haystack:
            return ["Check pedestal breaker.", "Inspect shore cable.", "Confirm charger status."]
        if "smoke" in haystack or "fire" in haystack:
            return ["Inspect cabin immediately.", "Disable heater if safe.", "Do not reset until cause is known."]
        return ["Inspect the reported device.", "Compare physical state with UI state.", "Review recent event history."]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_is(devices: Dict[str, Device], device_id: str, expected: Any) -> bool:
    device = devices.get(device_id)
    return device is not None and device.state is expected


def _severity_to_priority(severity: str) -> str:
    if severity == "critical":
        return "critical"
    if severity == "warning":
        return "high"
    if severity == "attention":
        return "normal"
    return "info"


def _severity_sort(severity: str) -> int:
    return {"critical": 0, "warning": 1, "attention": 2, "info": 3}.get(severity, 4)


def _rank(severity: str, confidence: float) -> int:
    base = {"critical": 400, "warning": 300, "attention": 200, "info": 100}.get(severity, 100)
    return base + int(confidence * 100)


def _runtime_seconds(device: Device) -> int:
    runtime = int(device.total_runtime_seconds or 0)
    if device.state is True and device.current_on_since:
        started = device.current_on_since
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        runtime += max(0, int((datetime.now(timezone.utc) - started).total_seconds()))
    return runtime


def _format_duration(seconds: int) -> str:
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min"
    hours = minutes // 60
    return f"{hours} hr {minutes % 60} min"
