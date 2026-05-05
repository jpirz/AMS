from app.services.event_service_sql import EventLogger
from app.services.device_service_sql import DeviceService
from app.services.scene_service_sql import SceneService
from app.services.system_state_sql import SystemState
from app.services.ai_state_sql import AIStateService
from app.services.ai_insights_service import AIInsightsService
from app.services.alarm_service_sql import AlarmService
from app.services.safety_service import SafetyService
from app.services.simulator_service import SimulatorService
from app.services.vessel_state_sql import VesselStateService
from app.hardware.manager import HardwareManager

event_logger = EventLogger()
hw_manager = HardwareManager()
device_service = DeviceService(hw_manager=hw_manager, event_logger=event_logger)
scene_service = SceneService(device_service=device_service, event_logger=event_logger)
system_state = SystemState()
ai_state = AIStateService()
alarm_service = AlarmService(device_service=device_service, event_logger=event_logger)
vessel_state = VesselStateService(event_logger=event_logger)
ai_insights = AIInsightsService(
    device_service=device_service,
    alarm_service=alarm_service,
    event_logger=event_logger,
    vessel_state=vessel_state,
    ai_state=ai_state,
)
safety_service = SafetyService(
    device_service=device_service,
    alarm_service=alarm_service,
    vessel_state=vessel_state,
    event_logger=event_logger,
)
simulator_service = SimulatorService(
    device_service=device_service,
    alarm_service=alarm_service,
    safety_service=safety_service,
    vessel_state=vessel_state,
)
