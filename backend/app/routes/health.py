from fastapi import APIRouter

from app.models.schemas import HealthResponse
from app.services.health_check import check_all_services

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health():
    services = await check_all_services()
    all_ok = all(s.healthy for s in services if s.name != "api")
    # API itself is up if we got here; overall Healthy when decoys respond
    status = "Healthy" if all_ok else "Degraded"
    return HealthResponse(status=status, services=services)
