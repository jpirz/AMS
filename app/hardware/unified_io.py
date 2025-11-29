from typing import Dict, Any
from .base_io import HardwareIO


class UnifiedHardwareIO(HardwareIO):
    """
    Hardware driver that understands hw_id strings like:
      - 'modbus:io_main:coil:0'
      - 'modbus:io_main:input:3'
      - 'gpio:17'

    Right now this just prints actions so you can develop
    without real hardware. Later: plug in pymodbus / GPIO here.
    """

    def __init__(self, hardware_config: Dict[str, Any]):
        self.hardware_config = hardware_config or {}
        self.modbus_buses = self._init_modbus_buses(
            self.hardware_config.get("buses", [])
        )

    def _init_modbus_buses(self, buses_config):
        buses = {}
        for bus in buses_config:
            if bus.get("type", "").startswith("modbus_"):
                buses[bus["id"]] = bus
        return buses

    def set_output(self, hw_id: str, value: bool) -> None:
        kind, rest = self._split_kind(hw_id)
        if kind == "modbus":
            self._set_modbus_output(rest, value)
        elif kind == "gpio":
            self._set_gpio_output(rest, value)
        else:
            print(f"[HW] Unknown kind '{kind}' for hw_id={hw_id} -> {value}")

    def get_input(self, hw_id: str) -> bool:
        kind, rest = self._split_kind(hw_id)
        if kind == "modbus":
            return self._get_modbus_input(rest)
        elif kind == "gpio":
            return self._get_gpio_input(rest)
        else:
            print(f"[HW] Unknown kind '{kind}' for hw_id={hw_id} -> returning False")
            return False

    def _split_kind(self, hw_id: str):
        parts = hw_id.split(":", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid hw_id format: {hw_id}")
        return parts[0], parts[1]

    def _parse_modbus_rest(self, rest: str):
        parts = rest.split(":")
        if len(parts) != 3:
            raise ValueError(f"Invalid modbus rest '{rest}'")
        bus_id, point_type, index_str = parts
        index = int(index_str)
        bus_cfg = self.modbus_buses.get(bus_id)
        if not bus_cfg:
            raise ValueError(f"Unknown modbus bus_id={bus_id}")
        return bus_cfg, point_type, index

    def _set_modbus_output(self, rest: str, value: bool):
        bus_cfg, point_type, index = self._parse_modbus_rest(rest)
        print(f"[MODBUS] bus={bus_cfg['id']} set {point_type}[{index}] = {value}")

    def _get_modbus_input(self, rest: str) -> bool:
        bus_cfg, point_type, index = self._parse_modbus_rest(rest)
        print(f"[MODBUS] bus={bus_cfg['id']} read {point_type}[{index}]")
        return False

    def _parse_gpio_rest(self, rest: str):
        return int(rest)

    def _set_gpio_output(self, rest: str, value: bool):
        pin = self._parse_gpio_rest(rest)
        print(f"[GPIO] set pin {pin} = {value}")

    def _get_gpio_input(self, rest: str) -> bool:
        pin = self._parse_gpio_rest(rest)
        print(f"[GPIO] read pin {pin}")
        return False
