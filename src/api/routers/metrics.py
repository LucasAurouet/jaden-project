from src.api.services.metrics import get_full_system_status

router = APIRouter(tags=["Statistiques"])

@router.get("/metrics/all")
async def get_all_metrics():
    return get_full_system_status()