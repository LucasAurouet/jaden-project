from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from typing import List, Dict, Any
from src.api.dependencies import verify_token
from src.api.services.file import FileService
from src.schemas import InspectWorkspaceRequest

router = APIRouter(tags=["Workspace & Fichiers"])

@router.post("/workspace/upload")
async def upload_file(
    file: UploadFile = File(...),
    session_id: str = Form(...),
    _token: str = Depends(verify_token)
) -> Dict[str, Any]:

    result = await FileService.feed_file_to_session(file, session_id)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])

    return result

@router.post("/workspace/inspect")
async def list_files(
    request: InspectWorkspaceRequest,
    _token: str = Depends(verify_token)
) -> List[Dict[str, Any]]:
    """
    Retourne la liste des documents présents dans le répertoire de travail de Maia.
    """
    workspace_data = FileService.list_workspace_files()

    sync_result = FileService.feed_workspace_to_session(
        session_id=request.session_id, 
        tree_string=workspace_data["tree"]
    )

    if sync_result["status"] == "error":
        print(f"Erreur de synchronisation SQLite : {sync_result['message']}")
        
    return workspace_data["files"]