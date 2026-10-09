import asyncio
from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import List, Dict, Any
from src.client.services import workspace
from src.client.services.workspace import WorkspaceError, WorkspaceUnavailable

router = APIRouter(tags=["Workspace"])


def _http_error(e: WorkspaceError) -> HTTPException:
    status = 503 if isinstance(e, WorkspaceUnavailable) else 400
    return HTTPException(status_code=status, detail=str(e))


@router.post("/workspace/upload")
async def upload_file(file: UploadFile = File(...)) -> Dict[str, Any]:
    # Un octet de plus que la limite suffit à détecter un fichier trop gros
    # sans le charger entièrement en mémoire.
    content = await file.read(workspace.MAX_UPLOAD_SIZE + 1)
    try:
        path = await asyncio.to_thread(workspace.save_upload, file.filename, content)
    except WorkspaceError as e:
        raise _http_error(e)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Écriture impossible : {e}")
    return {"path": path}

# Route synchrone (def) : FastAPI l'exécute dans un threadpool, le parcours
# du disque ne bloque donc pas la boucle asyncio.
@router.get("/workspace/inspect")
def list_files() -> List[Dict[str, Any]]:
    try:
        return workspace.list_files()
    except WorkspaceError as e:
        raise _http_error(e)
