from fastapi import APIRouter, Depends, File, Form, UploadFile
from typing import Any, Dict, List
from src.client.dependencies import relay_error, session_token
from src.client.services import homn
from src.client.services.homn import ServerError

router = APIRouter(tags=["Documents"])


@router.post("/documents", status_code=201)
async def upload_document(
    file: UploadFile = File(...), shared: bool = Form(False), token: str = Depends(session_token),
) -> Dict[str, Any]:
    # La taille, le format et le droit de partager sont vérifiés par le serveur.
    try:
        return await homn.upload_document(token, file.filename, await file.read(), file.content_type, shared)
    except ServerError as e:
        raise relay_error(e)


@router.get("/documents")
async def list_documents(token: str = Depends(session_token)) -> List[Dict[str, Any]]:
    try:
        return await homn.list_documents(token)
    except ServerError as e:
        raise relay_error(e)


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(document_id: int, token: str = Depends(session_token)):
    try:
        await homn.delete_document(token, document_id)
    except ServerError as e:
        raise relay_error(e)
