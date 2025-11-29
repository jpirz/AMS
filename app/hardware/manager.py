import json
from typing import Dict

from app.db import get_connection
from app.hardware.base_io import HardwareIO
from app.hardware.unified_io import UnifiedHardwareIO


class HardwareManager:
    """
    Lazily builds a UnifiedHardwareIO per yacht from hardware_json in DB.
    Caches them so you don't recreate hardware clients on every call.
    """

    def __init__(self):
        self._io_by_yacht: Dict[str, HardwareIO] = {}

    def get_io(self, yacht_id: str) -> HardwareIO:
        if yacht_id in self._io_by_yacht:
            return self._io_by_yacht[yacht_id]

        hardware_cfg = self._load_hardware_config(yacht_id)
        io = UnifiedHardwareIO(hardware_cfg)
        self._io_by_yacht[yacht_id] = io
        return io

    def _load_hardware_config(self, yacht_id: str):
        conn = get_connection()
        try:
            cur = conn.execute(
                "SELECT hardware_json FROM yachts WHERE id = ?",
                (yacht_id,),
            )
            row = cur.fetchone()
        finally:
            conn.close()

        if row is None:
            raise ValueError(f"Yacht '{yacht_id}' not found in DB")

        if row["hardware_json"] is None:
            return {}

        return json.loads(row["hardware_json"])
