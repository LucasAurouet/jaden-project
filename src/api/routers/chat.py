from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from src.api.dependencies import verify_token
from src.api.services.chat import ChatService
from src.schemas import ComputeRequest

router = APIRouter(tags=["Conversations"])

# Empêche un éventuel reverse proxy (nginx sur un VPS) de bufferiser le flux.
SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


@router.post("/compute")
async def compute(request: ComputeRequest, _token: str = Depends(verify_token)) -> StreamingResponse:
    return StreamingResponse(
        ChatService.stream_compute(session_id=request.session_id, prompt=request.prompt),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
