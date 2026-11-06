from fastapi import APIRouter, Depends
from typing import Dict, Any
from src.client.dependencies import session_token
from src.client.services import homn

router = APIRouter(tags=["Statistiques"])

@router.get("/metrics")
async def metrics(token: str = Depends(session_token)) -> Dict[str, Any]:
    return await homn.get_server_metrics(token)
