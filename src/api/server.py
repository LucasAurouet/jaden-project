from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import APIKeyHeader
import logging
from config import MAIA_KEY, SERVER_PORT, SERVER_NAME
from src.schemas import ComputeRequest
from src.core.inference import run_inference
import uuid

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
    # On génère un ID unique par requête pour voir si c'est la même qui tourne
    req_id = uuid.uuid4().hex[:6]
    print(f"\n[FARTAPI - {req_id}] Reçu le prompt: '{request.prompt}'")
    
    url = "http://127.0.0.1:8080/v1/chat/completions"
    print(f"[FASTAPI - {req_id}] Envoi de la requête à llama.cpp sur {url}...")
    
    res = await run_inference(request.prompt, url)
    
    print(f"[FASTAPI - {req_id}] Réponse reçue de run_inference: '{res[:30]}...'")
    return res

@app.get("/health")
async def health():
    return {"status": "ok"}