import uvicorn
from fastapi import FastAPI

from app.routers import ai
from app.db import init_db
from app.api import devices, scenes, events, system, provision
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db import init_db
from app.api import devices, scenes, events, system, provision

# Initialize SQLite schema
init_db()

app = FastAPI(title="YachtOS Backend (SQLite + Multi-Yacht)")

# API routers
app.include_router(devices.router)
app.include_router(scenes.router)
app.include_router(events.router)
app.include_router(system.router)
app.include_router(provision.router)
app.include_router(ai.router)

# Static web UI
app.mount("/ui", StaticFiles(directory="web", html=True), name="ui")


@app.get("/")
async def root():
    return {
        "message": "YachtOS backend running",
        "ui": "/ui",
        "endpoints": [
            "/provision/yacht",
            "/yachts/{yacht_id}/devices",
            "/yachts/{yacht_id}/scenes",
            "/yachts/{yacht_id}/events",
            "/yachts/{yacht_id}/system/ai-mode",
        ],
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
