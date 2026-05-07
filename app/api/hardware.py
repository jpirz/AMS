from fastapi import APIRouter

from app.services.core import hardware_status

router = APIRouter(prefix="/yachts/{yacht_id}/hardware", tags=["hardware"])


@router.get("/health")
def hardware_health(yacht_id: str):
    return hardware_status.health_summary(yacht_id)
