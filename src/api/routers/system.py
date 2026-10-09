from fastapi import APIRouter

router = APIRouter(tags=["Système"])

@router.get("/health")
async def health():
    return {"status": "ok", "service": "homn-backend"}
