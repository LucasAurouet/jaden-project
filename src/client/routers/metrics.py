from fastapi import APIRouter
from typing import Dict, Any
from src.client.services import maia

router = APIRouter(tags=["Statistiques"])

@router.get("/metrics")
async def metrics() -> Dict[str, Any]:
    # Relais vers le serveur GPU : le navigateur n'a pas besoin de la clé.
    return await maia.get_server_metrics()
