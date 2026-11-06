from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from typing import Any, Dict, List
from src.api.dependencies import get_current_user
from src.api.services import database, rag
from src.api.services.rag import DocumentError, DuplicateDocument
from src.api.services.embeddings import EmbeddingError

router = APIRouter(tags=["Documents (RAG)"])


@router.post("/documents", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    shared: bool = Form(False),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    # Les documents partagés, visibles de tous, sont gérés par l'admin.
    if shared and not user["is_admin"]:
        raise HTTPException(status_code=403, detail="Seul un admin peut ajouter un document partagé.")
    # Un octet de plus que la limite suffit à détecter un fichier trop gros
    # sans le charger entièrement en mémoire.
    content = await file.read(rag.MAX_UPLOAD_SIZE + 1)
    try:
        return await rag.ingest(None if shared else user["id"], user["id"], file.filename, content)
    except DuplicateDocument as e:
        raise HTTPException(status_code=409, detail=str(e))
    except DocumentError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except EmbeddingError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/documents")
async def list_documents(user: Dict[str, Any] = Depends(get_current_user)) -> List[Dict[str, Any]]:
    return await database.list_documents(user["id"])


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(document_id: int, user: Dict[str, Any] = Depends(get_current_user)):
    document = await database.get_visible_document(document_id, user["id"])
    if document is None:
        raise HTTPException(status_code=404, detail="Document introuvable.")
    if document["shared"] and not user["is_admin"]:
        raise HTTPException(status_code=403, detail="Seul un admin peut retirer un document partagé.")
    await database.delete_document(document_id)
