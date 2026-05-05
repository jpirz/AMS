from typing import Any, Dict, List

from app.services.alarm_service_sql import AlarmService
from app.services.device_service_sql import DeviceService
from app.services.safety_service import SafetyService
from app.services.vessel_state_sql import VesselStateService


SCENARIOS: Dict[str, Dict[str, Any]] = {
    "normal": {
        "mode": "in_port",
        "states": {
            "shore_power_present": True,
            "battery_low_alarm": False,
            "battery_voltage_house": 12.7,
            "bilge_float_high": False,
            "smoke_cabin": False,
        },
    },
    "bilge_high": {"states": {"bilge_float_high": True}},
    "low_battery": {"states": {"battery_voltage_house": 10.9, "battery_low_alarm": True}},
    "shore_power_loss": {"mode": "unattended", "states": {"shore_power_present": False}},
    "smoke_alarm": {"states": {"smoke_cabin": True}},
    "underway": {"mode": "underway", "states": {"nav_lights": False, "anchor_light": True}},
    "at_anchor": {"mode": "at_anchor", "states": {"anchor_light": False, "nav_lights": True}},
}


class SimulatorService:
    def __init__(
        self,
        device_service: DeviceService,
        alarm_service: AlarmService,
        safety_service: SafetyService,
        vessel_state: VesselStateService,
    ):
        self.devices = device_service
        self.alarms = alarm_service
        self.safety = safety_service
        self.vessel_state = vessel_state

    def list_scenarios(self) -> List[str]:
        return sorted(SCENARIOS.keys())

    def run_scenario(self, yacht_id: str, scenario_id: str) -> Dict[str, Any]:
        scenario = SCENARIOS.get(scenario_id)
        if scenario is None:
            raise KeyError(scenario_id)

        if "mode" in scenario:
            self.vessel_state.set_mode(yacht_id, scenario["mode"], source="simulator")

        applied = []
        for device_id, state in scenario.get("states", {}).items():
            device = self.devices.set_device_state(
                yacht_id=yacht_id,
                source="simulator",
                device_id=device_id,
                state=state,
            )
            self.alarms.sync_device(yacht_id, device_id, device=device)
            applied.append({"device_id": device_id, "state": state})

        safety = self.safety.enforce(yacht_id, source="simulator")
        return {
            "status": "ok",
            "scenario": scenario_id,
            "applied": applied,
            "safety": safety,
        }
