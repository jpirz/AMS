from app.services.event_service_sql import EventLogger
from app.services.device_service_sql import DeviceService
from app.services.scene_service_sql import SceneService
from app.services.system_state_sql import SystemState
from app.hardware.manager import HardwareManager

event_logger = EventLogger()
hw_manager = HardwareManager()
device_service = DeviceService(hw_manager=hw_manager, event_logger=event_logger)
scene_service = SceneService(device_service=device_service, event_logger=event_logger)
system_state = SystemState()
