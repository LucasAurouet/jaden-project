from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from src.client.services import homn
from src.client.services.homn import ServerError
from src.schemas import ComputeRequest

router = APIRouter(tags=["Conversations"])


@router.post("/compute")
async def compute(request: ComputeRequest) -> StreamingResponse:
    # Les erreurs survenues pendant le flux arrivent sous forme d'événements "error".
    try:
        upstream = await homn.compute(session_id=request.session_id, prompt=request.prompt)
    except ServerError as e:
        raise HTTPException(status_code=e.status, detail=str(e))
    return StreamingResponse(
        upstream.aiter_raw(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
        background=BackgroundTask(upstream.aclose),
    )
