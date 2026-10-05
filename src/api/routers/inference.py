import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask
from src.api.dependencies import verify_token
from src.api.services.inference import get_client

router = APIRouter(tags=["Inférence (compatible OpenAI)"])


def _error(status: int, message: str, kind: str) -> JSONResponse:
    # Même format d'erreur que l'API OpenAI, pour que les clients le comprennent.
    return JSONResponse(status_code=status, content={"error": {"message": message, "type": kind}})


async def _forward(method: str, path: str, body: bytes | None = None):
    """
    Transmet la requête à llama-server sans l'interpréter, et renvoie sa réponse
    octet par octet. Le serveur reste une "coquille" : messages, tools,
    stream, température... tout passe tel quel. Comme la réponse est relayée au
    fil de l'eau, le streaming (stream: true) fonctionne sans code particulier.
    """
    client = get_client()
    upstream_request = client.build_request(
        method, path, content=body, headers={"Content-Type": "application/json"}
    )
    try:
        upstream = await client.send(upstream_request, stream=True)
    except httpx.ConnectError:
        return _error(502, "Le moteur d'inférence (llama-server) est injoignable.", "upstream_unavailable")
    except httpx.TimeoutException:
        return _error(504, "Le moteur d'inférence n'a pas répondu à temps.", "upstream_timeout")

    return StreamingResponse(
        upstream.aiter_raw(),
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type"),
        # Ferme la connexion vers llama-server une fois la réponse envoyée.
        background=BackgroundTask(upstream.aclose),
    )


@router.post("/chat/completions")
async def chat_completions(request: Request, _token: str = Depends(verify_token)):
    return await _forward("POST", "/v1/chat/completions", await request.body())


@router.get("/models")
async def list_models(_token: str = Depends(verify_token)):
    return await _forward("GET", "/v1/models")
