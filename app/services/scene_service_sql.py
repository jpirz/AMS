import json
from typing import List

from app.db import get_connection
from app.models import Scene, SceneAction
from app.services.event_service_sql import EventLogger
from app.services.device_service_sql import DeviceService


class SceneService:
    def __init__(self, device_service: DeviceService, event_logger: EventLogger):
        self.device_service = device_service
        self.events = event_logger

    def list_scenes(self, yacht_id: str) -> List[Scene]:
        conn = get_connection()
        try:
            cur = conn.execute(
                "SELECT yacht_id, id, name, description "
                "FROM scenes WHERE yacht_id = ?",
                (yacht_id,),
            )
            rows = cur.fetchall()
        finally:
            conn.close()

        scenes: List[Scene] = []
        for r in rows:
            actions = self._load_actions(yacht_id, r["id"])
            scenes.append(
                Scene(
                    yacht_id=r["yacht_id"],
                    id=r["id"],
                    name=r["name"],
                    description=r["description"],
                    actions=actions,
                )
            )
        return scenes

    def get_scene(self, yacht_id: str, scene_id: str) -> Scene:
        conn = get_connection()
        try:
            cur = conn.execute(
                "SELECT yacht_id, id, name, description "
                "FROM scenes WHERE yacht_id = ? AND id = ?",
                (yacht_id, scene_id),
            )
            row = cur.fetchone()
        finally:
            conn.close()

        if row is None:
            raise KeyError(scene_id)

        actions = self._load_actions(yacht_id, scene_id)
        return Scene(
            yacht_id=row["yacht_id"],
            id=row["id"],
            name=row["name"],
            description=row["description"],
            actions=actions,
        )

    def _load_actions(self, yacht_id: str, scene_id: str) -> List[SceneAction]:
        conn = get_connection()
        try:
            cur = conn.execute(
                "SELECT device_id, state FROM scene_actions "
                "WHERE yacht_id = ? AND scene_id = ? ORDER BY order_index ASC",
                (yacht_id, scene_id),
            )
            rows = cur.fetchall()
        finally:
            conn.close()

        actions: List[SceneAction] = []
        for r in rows:
            actions.append(
                SceneAction(
                    device_id=r["device_id"],
                    state=json.loads(r["state"]),
                )
            )
        return actions

    def activate_scene(self, yacht_id: str, source: str, scene_id: str) -> Scene:
        scene = self.get_scene(yacht_id, scene_id)

        for action in scene.actions:
            self.device_service.set_device_state(
                yacht_id=yacht_id,
                source=source,
                device_id=action.device_id,
                state=action.state,
            )

        self.events.log(
            yacht_id=yacht_id,
            source=source,
            type="scene_activation",
            details={"scene_id": scene_id},
        )

        return scene
