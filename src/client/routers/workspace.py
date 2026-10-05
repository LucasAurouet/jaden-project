from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import List, Dict, Any
from src.client.services.file import FileService

router = APIRouter(tags=["Workspace & Fichiers"])

@router.post("/workspace/upload")
async def upload_file(
    file: UploadFile = File(...),
    session_id: str = Form(...),
) -> Dict[str, Any]:
    result = await FileService.feed_file_to_session(file, session_id)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return result

# Route synchrone (def) : FastAPI l'exécute dans un threadpool, le parcours
# du disque ne bloque donc pas la boucle asyncio.
@router.get("/workspace/inspect")
def list_files() -> List[Dict[str, Any]]:
    return FileService.list_workspace_files()["files"]
