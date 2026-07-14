from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import APIKeyHeader

from config import MAIA_KEY, SERVER_PORT, SERVER_NAME
from src.schemas import ComputeRequest
from src.core.inference import run_inference

app = FastAPI(title="MAIA Server")

_api_key_header = APIKeyHeader(name="maia-token", auto_error=False)


async def _verify_token(api_key: str = Depends(_api_key_header)) -> str:
    if api_key != MAIA_KEY:
        raise HTTPException(status_code=403, detail="Clé MAIA invalide")
    return api_key


@app.post("/v1/compute")
async def compute(
    request: ComputeRequest,
    _token: str = Depends(_verify_token),
) -> str:
    
    url = f"http://127.0.0.1:{SERVER_PORT}/v1/chat/completions"

    return run_inference(url, request.prompt)