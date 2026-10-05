from fastapi import APIRouter, Depends
from src.api.dependencies import verify_token
from src.api.services.metrics import get_full_system_status

router = APIRouter(tags=["Statistiques"])

@router.get("/metrics/all")
async def get_all_metrics(_token: str = Depends(verify_token)):
    return await get_full_system_status()
