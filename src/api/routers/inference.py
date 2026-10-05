import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from src.api.dependencies import verify_token
from src.api.services.inference import forward

router = APIRouter(tags=["Inférence (compatible OpenAI)"])


def _relay(upstream: httpx.Response) -> StreamingResponse:
    return StreamingResponse(
        upstream.aiter_raw(),
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type"),
        background=BackgroundTask(upstream.aclose),
    )


@router.post("/chat/completions")
async def chat_completions(request: Request, _token: str = Depends(verify_token)):
    return _relay(await forward("POST", "/v1/chat/completions", await request.body()))


@router.get("/models")
async def list_models(_token: str = Depends(verify_token)):
    return _relay(await forward("GET", "/v1/models"))
