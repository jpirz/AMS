from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.core import scene_service

router = APIRouter(prefix="/yachts/{yacht_id}/scenes", tags=["scenes"])


class ActivateSceneRequest(BaseModel):
    source: str = "user_ui"


@router.get("/")
def list_scenes(yacht_id: str):
    return scene_service.list_scenes(yacht_id=yacht_id)


@router.get("/{scene_id}")
def get_scene(yacht_id: str, scene_id: str):
    try:
        return scene_service.get_scene(yacht_id=yacht_id, scene_id=scene_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Scene not found")


@router.post("/{scene_id}/activate")
def activate_scene(yacht_id: str, scene_id: str, body: ActivateSceneRequest):
    try:
        return scene_service.activate_scene(
            yacht_id=yacht_id,
            source=body.source,
            scene_id=scene_id,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Scene not found")
