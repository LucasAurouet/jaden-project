from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from typing import Any, Dict, List
from src.api.dependencies import verify_token
from src.api.services import database, rag
from src.api.services.rag import DocumentError
from src.api.services.embeddings import EmbeddingError

router = APIRouter(tags=["Documents (RAG)"], dependencies=[Depends(verify_token)])


@router.post("/documents", status_code=201)
async def upload_document(file: UploadFile = File(...)) -> Dict[str, Any]:
    # Un octet de plus que la limite suffit à détecter un fichier trop gros
    # sans le charger entièrement en mémoire.
    content = await file.read(rag.MAX_UPLOAD_SIZE + 1)
    try:
        return await rag.ingest(file.filename, content)
    except DocumentError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except EmbeddingError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/documents")
async def list_documents() -> List[Dict[str, Any]]:
    return await database.list_documents()


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(document_id: int):
    if not await database.delete_document(document_id):
        raise HTTPException(status_code=404, detail="Document introuvable.")
