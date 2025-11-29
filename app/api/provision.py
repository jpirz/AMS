from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List

from app.services.config_loader_sql import provision_yacht

router = APIRouter(prefix="/provision", tags=["provision"])


class YachtConfig(BaseModel):
    yacht: Dict[str, Any]
    hardware: Dict[str, Any] = {}
    devices: List[Dict[str, Any]] = []
    scenes: List[Dict[str, Any]] = []


@router.post("/yacht")
def provision_yacht_endpoint(cfg: YachtConfig):
    try:
        provision_yacht(cfg.dict())
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
