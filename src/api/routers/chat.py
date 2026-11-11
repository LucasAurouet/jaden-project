from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from typing import Any, Dict
from src.api.dependencies import get_current_user
from src.api.services import database
from src.api.services.chat import ChatService
from src.schemas import ComputeRequest

router = APIRouter(tags=["Conversations"])

# Empêche un éventuel reverse proxy (nginx sur un VPS) de bufferiser le flux.
SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


@router.post("/compute")
async def compute(request: ComputeRequest, user: Dict[str, Any] = Depends(get_current_user)) -> StreamingResponse:
    # Vérifié avant d'ouvrir le flux, pour renvoyer un vrai 404. save_exchange
    # revérifie à l'enregistrement.
    if await database.session_belongs_to_other(request.session_id, user["id"]):
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return StreamingResponse(
        ChatService.stream_compute(user_id=user["id"], session_id=request.session_id, prompt=request.prompt),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
