from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import require_control_auth
from app.services.core import simulator_service

router = APIRouter(prefix="/yachts/{yacht_id}/simulator", tags=["simulator"])


class RunScenarioRequest(BaseModel):
    scenario: str


@router.get("/scenarios")
def list_scenarios(yacht_id: str):
    return {"yacht_id": yacht_id, "scenarios": simulator_service.list_scenarios()}


@router.post("/run", dependencies=[Depends(require_control_auth)])
def run_scenario(yacht_id: str, body: RunScenarioRequest):
    try:
        return simulator_service.run_scenario(yacht_id, body.scenario)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown scenario")
