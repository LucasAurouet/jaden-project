from fastapi import APIRouter
from typing import Dict, Any
from src.client.services import homn

router = APIRouter(tags=["Statistiques"])

@router.get("/metrics")
async def metrics() -> Dict[str, Any]:
    return await homn.get_server_metrics()
