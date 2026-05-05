from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import require_control_auth
from app.services.core import safety_service, vessel_state

router = APIRouter(prefix="/yachts/{yacht_id}/mode", tags=["mode"])


class SetModeRequest(BaseModel):
    mode: str
    source: str = "user_ui"


@router.get("/")
def get_mode(yacht_id: str):
    return {"yacht_id": yacht_id, "mode": vessel_state.get_mode(yacht_id)}


@router.post("/", dependencies=[Depends(require_control_auth)])
def set_mode(yacht_id: str, body: SetModeRequest):
    try:
        result = vessel_state.set_mode(yacht_id, body.mode, source=body.source)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    result["safety"] = safety_service.enforce(yacht_id)
    return result
