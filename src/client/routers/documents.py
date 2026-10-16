from fastapi import APIRouter, File, HTTPException, UploadFile
from typing import Any, Dict, List
from src.client.services import homn
from src.client.services.homn import ServerError

router = APIRouter(tags=["Documents"])


@router.post("/documents", status_code=201)
async def upload_document(file: UploadFile = File(...)) -> Dict[str, Any]:
    # La taille et le format sont vérifiés par le serveur.
    try:
        return await homn.upload_document(file.filename, await file.read(), file.content_type)
    except ServerError as e:
        raise HTTPException(status_code=e.status, detail=str(e))


@router.get("/documents")
async def list_documents() -> List[Dict[str, Any]]:
    try:
        return await homn.list_documents()
    except ServerError as e:
        raise HTTPException(status_code=e.status, detail=str(e))


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(document_id: int):
    try:
        await homn.delete_document(document_id)
    except ServerError as e:
        raise HTTPException(status_code=e.status, detail=str(e))
