from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from typing import List, Dict, Any
from src.api.dependencies import verify_token
from src.api.services.file_service import FileService
router = APIRouter(tags=["Workspace & Fichiers"])

@router.post("/workspace/upload")
async def upload_file(
    file: UploadFile = File(...),
    _token: str = Depends(verify_token)
) -> Dict[str, Any]:

    result = await FileService.save_uploaded_file(file)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
        
    return result

@router.get("/workspace/files")
async def list_files(
    _token: str = Depends(verify_token)
) -> List[Dict[str, Any]]:
    """
    Retourne la liste des documents présents dans le répertoire de travail de Maia.
    Très utile pour l'affichage dans ton UI de fichiers disponibles.
    """
    return FileService.list_workspace_files()