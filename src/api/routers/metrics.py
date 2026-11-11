from fastapi import APIRouter, Depends
from src.api.dependencies import get_current_user
from src.api.services.metrics import get_full_system_status

router = APIRouter(tags=["Metrics"])

@router.get("/metrics/all")
async def get_all_metrics(_user=Depends(get_current_user)):
    return await get_full_system_status()
