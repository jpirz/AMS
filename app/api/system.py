from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth import require_admin_auth
from app.services.core import system_state
from app.models import AiMode

router = APIRouter(prefix="/yachts/{yacht_id}/system", tags=["system"])


class SetAiModeRequest(BaseModel):
    mode: AiMode


@router.get("/ai-mode")
def get_ai_mode(yacht_id: str):
    return {"mode": system_state.get_ai_mode(yacht_id)}


@router.post("/ai-mode", dependencies=[Depends(require_admin_auth)])
def set_ai_mode(yacht_id: str, body: SetAiModeRequest):
    system_state.set_ai_mode(yacht_id, body.mode)
    return {"mode": system_state.get_ai_mode(yacht_id)}
