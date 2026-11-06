from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from src.client.dependencies import relay_error, session_token
from src.client.services import homn
from src.client.services.homn import ServerError
from src.schemas import ComputeRequest

router = APIRouter(tags=["Conversations"])


@router.post("/compute")
async def compute(request: ComputeRequest, token: str = Depends(session_token)) -> StreamingResponse:
    # Les erreurs survenues pendant le flux arrivent sous forme d'événements "error".
    try:
        upstream = await homn.compute(token, session_id=request.session_id, prompt=request.prompt)
    except ServerError as e:
        raise relay_error(e)
    return StreamingResponse(
        upstream.aiter_raw(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        background=BackgroundTask(upstream.aclose),
    )
