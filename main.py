# main.py

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from collections import defaultdict, deque
from typing import Deque, Dict, List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.db import init_db

# Old-style modules that are still fine as-is
from app.api import events, system, provision

# New multi-yacht routers
from app.routers import devices, scenes, ai, yachts


# ----------------------
# AI watchkeeper logs (in-memory per yacht)
# ----------------------

class AIWatchkeeperLog(BaseModel):
    generated_at: datetime
    summary: str
    actions: List[dict]
    mode: Optional[str] = None


AI_LOGS: Dict[str, Deque[AIWatchkeeperLog]] = defaultdict(
    lambda: deque(maxlen=200)
)

# ----------------------
# App init
# ----------------------

# Initialize SQLite schema
init_db()

app = FastAPI(title="YachtOS Backend (SQLite + Multi-Yacht)")

# Routers: new multi-yacht ones first
app.include_router(devices.router)   # /yachts/{yacht_id}/devices
app.include_router(scenes.router)    # /yachts/{yacht_id}/scenes
app.include_router(ai.router)        # /yachts/{yacht_id}/ai/...

# Legacy / utility routers
app.include_router(events.router)
app.include_router(system.router)
app.include_router(provision.router)

# Yachts metadata router
app.include_router(yachts.router)    # /yachts, /yachts/{yacht_id}/meta

# Static web UI
app.mount("/ui", StaticFiles(directory="web", html=True), name="ui")


@app.get("/")
async def root():
    return {
        "message": "YachtOS backend running",
        "ui": "/ui",
        "endpoints": [
            "/provision/yacht",
            "/yachts",
            "/yachts/{yacht_id}/meta",
            "/yachts/{yacht_id}/devices",
            "/yachts/{yacht_id}/scenes",
            "/yachts/{yacht_id}/events",
            "/yachts/{yacht_id}/system/ai-mode",
            "/yachts/{yacht_id}/ai/logs",
        ],
    }


@app.post("/yachts/{yacht_id}/ai/logs")
async def add_ai_log(yacht_id: str, log: AIWatchkeeperLog):
    """
    Called by ai_watchkeeper.py every cycle with a human-readable summary.
    """
    AI_LOGS[yacht_id].appendleft(log)
    return {"status": "ok"}


@app.get("/yachts/{yacht_id}/ai/logs")
async def get_ai_logs(yacht_id: str, limit: int = 50):
    """
    UI uses this to show recent AI decisions.
    """
    logs = list(AI_LOGS[yacht_id])[:limit]
    return logs


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
