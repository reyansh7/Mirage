from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.routes import command, events, health, sessions
from app.world.loader import get_world


def _resolve_frontend() -> Path | None:
    candidates = [
        Path("/app/frontend"),  # Docker image
        Path(__file__).resolve().parents[2].parent / "frontend",  # repo checkout
        Path(__file__).resolve().parents[1] / "static",
    ]
    for path in candidates:
        if path.is_dir() and (path / "index.html").exists():
            return path
    return None


FRONTEND = _resolve_frontend()


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    get_world()
    yield


app = FastAPI(
    title="Adaptive Honeypot — Event Collector",
    description="Phase 3: session engine + structured event flight recorder + live dashboard",
    version="0.3.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(events.router)
app.include_router(sessions.router)
app.include_router(command.router)

if FRONTEND is not None:
    assets = FRONTEND / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/")
    async def dashboard_root():
        return FileResponse(FRONTEND / "index.html")

    @app.get("/dashboard")
    async def dashboard_alias():
        return FileResponse(FRONTEND / "index.html")
