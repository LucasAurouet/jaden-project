"""
Responsabilité unique : définir les routes HTTP et l'authentification.
Aucun appel direct à Ollama, psutil ou logique métier ici.
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import StreamingResponse
from fastapi.security import APIKeyHeader

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
) -> StreamingResponse:
    async def _stream():
        try:
            async for chunk in stream_inference(request.prompt, request.expert_type):
                yield chunk
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Ollama indisponible : {e}")

    return StreamingResponse(_stream(), media_type="text/plain")