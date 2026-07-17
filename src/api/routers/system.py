import os
from fastapi import APIRouter

router = APIRouter(tags=["Système"])

static_path = os.path.join(os.path.dirname(__file__), "../../client/static")

@router.get("/health")
async def health():
    return {"status": "ok", "service": "maia-backend"}
