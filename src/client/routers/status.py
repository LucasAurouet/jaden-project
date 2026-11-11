from fastapi import APIRouter
from typing import Dict
from src.client.services import jaden

router = APIRouter(tags=["Status"])


@router.get("/status")
async def status() -> Dict[str, bool]:
    """État de la liaison avec le serveur, pour le voyant de l'interface."""
    return {"server": await jaden.server_reachable()}
