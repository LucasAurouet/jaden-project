import os
from fastapi import APIRouter
from src.schemas import SystemMetrics
from src.api.services.system import get_system_metrics
from src.api.services.inference import get_llama_metrics_from_api

router = APIRouter(tags=["Système"])

static_path = os.path.join(os.path.dirname(__file__), "../../client/static")

@router.get("/health")
async def health():
    return {"status": "ok", "service": "maia-backend"}

@router.get("/metrics", response_model=SystemMetrics)
async def system_metrics():
    system = get_system_metrics()
    llama = await get_llama_metrics_from_api()
    return SystemMetrics(**system, llama=llama)