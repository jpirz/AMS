# main.py

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db import init_db
from app.services.config_loader_sql import seed_known_yacht_profiles

# SQLite-backed API modules
from app.api import alarms, devices, events, mode, provision, scenes, simulator, system

from app.ai.router import router as ai_router
from app.routers import yachts

# ----------------------
# App init
# ----------------------

# Initialize SQLite schema
init_db()
seed_known_yacht_profiles()

app = FastAPI(title="YachtOS Backend (SQLite + Multi-Yacht)")

# Live control routes use SQLite-backed services.
app.include_router(devices.router)   # /yachts/{yacht_id}/devices
app.include_router(scenes.router)    # /yachts/{yacht_id}/scenes
app.include_router(ai_router)        # /yachts/{yacht_id}/ai/...
app.include_router(alarms.router)    # /yachts/{yacht_id}/alarms
app.include_router(mode.router)      # /yachts/{yacht_id}/mode
app.include_router(simulator.router) # /yachts/{yacht_id}/simulator

# Utility routers
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
            "/yachts/{yacht_id}/alarms/active",
            "/yachts/{yacht_id}/mode",
            "/yachts/{yacht_id}/simulator/scenarios",
            "/yachts/{yacht_id}/system/ai-mode",
            "/yachts/{yacht_id}/ai/status",
            "/yachts/{yacht_id}/ai/suggestions",
            "/yachts/{yacht_id}/ai/nl-command",
            "/yachts/{yacht_id}/ai/incidents",
            "/yachts/{yacht_id}/ai/maintenance",
            "/yachts/{yacht_id}/ai/logs",
            "/yachts/{yacht_id}/ai/commands",
        ],
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
