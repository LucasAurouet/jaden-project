from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import APIKeyHeader
from src.api.database import init_db, save_message, get_chat_history
from config import MAIA_KEY, SERVER_PORT, SERVER_NAME
from src.schemas import ComputeRequest
from src.api.inference import run_inference
import uuid

app = FastAPI(title="MAIA Server")

_api_key_header = APIKeyHeader(name="maia-token", auto_error=False)


async def _verify_token(api_key: str = Depends(_api_key_header)) -> str:
    if api_key != MAIA_KEY:
        raise HTTPException(status_code=403, detail="Clé MAIA invalide")
    return api_key

@app.on_event("startup")
def startup_event():
    init_db()
    print("Base de données SQLite initialisée avec succès.")

@app.post("/v1/compute")
async def compute(
    request: ComputeRequest,
    _token: str = Depends(_verify_token),
) -> str:
    
    save_message(request.session_id, "user", request.prompt)
    history = get_chat_history(request.session_id)
    messages = [{"role": "system", "content": "Tu es un assistant développeur."}] + history

    url = "http://127.0.0.1:8080/v1/chat/completions"
    assistant_response = await run_inference(messages, url)
    
    if not assistant_response.startswith("[Erreur]"):
        save_message(request.session_id, "assistant", assistant_response)
        
    return assistant_response

@app.get("/health")
async def health():
    return {"status": "ok"}