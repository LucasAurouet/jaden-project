import os
from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(tags=["Système"])

static_path = os.path.join(os.path.dirname(__file__), "../../client/static")

@router.get("/health")
async def health():
    return {"status": "ok", "service": "maia-backend"}

@router.get("/")
async def read_index():
    index_file = os.path.join(static_path, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"status": "error", "message": f"Le fichier index.html est introuvable à l'adresse : {index_file}"}