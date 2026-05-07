from fastapi import APIRouter, Query

from app.services.core import sensor_history

router = APIRouter(prefix="/yachts/{yacht_id}/history", tags=["history"])


@router.get("/sensors/{device_id}")
def sensor_history_endpoint(
    yacht_id: str,
    device_id: str,
    limit: int = Query(200, ge=1, le=2000),
):
    return sensor_history.list_history(yacht_id, device_id, limit=limit)


@router.get("/sensors")
def latest_sensor_history(yacht_id: str):
    return {"yacht_id": yacht_id, "sensors": sensor_history.latest_by_sensor(yacht_id)}
