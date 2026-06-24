"""
Responsabilité unique : définir les routes HTTP et l'authentification.
Aucun appel direct à Ollama, psutil ou logique métier ici.
"""

import json

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import APIKeyHeader
from sse_starlette.sse import EventSourceResponse

from config import MAIA_KEY
from src.schemas import ComputeRequest
from src.core.inference import stream_inference

app = FastAPI(title="MAIA Agent Node")

_api_key_header = APIKeyHeader(name="maia-token", auto_error=False)


async def _verify_token(api_key: str = Depends(_api_key_header)) -> str:
    if api_key != MAIA_KEY:
        raise HTTPException(status_code=403, detail="Clé MAIA invalide")
    return api_key


@app.post("/v1/compute")
async def compute(
    request: ComputeRequest,
    _token: str = Depends(_verify_token),
) -> EventSourceResponse:
    async def _stream():
        try:
            async for event in stream_inference(request.prompt, request.expert_type):
                if event["type"] == "text":
                    yield {"event": "text", "data": event["data"]}
                elif event["type"] == "metrics":
                    yield {"event": "metrics", "data": json.dumps(event["data"])}
        except Exception as e:
            yield {"event": "error", "data": str(e)}

    return EventSourceResponse(_stream())