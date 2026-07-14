from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import APIKeyHeader
from src.api.database import init_db, save_message, get_chat_history
from config import MAIA_KEY, SERVER_PORT, SERVER_NAME
from src.schemas import ComputeRequest, ComputeResponse
from src.api.inference import run_inference
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from pydantic import ValidationError


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    print("Base de données SQLite initialisée avec succès.")
    
    yield
    
    print("Fermeture du serveur")


app = FastAPI(title="MAIA Server", lifespan=lifespan)

_api_key_header = APIKeyHeader(name="maia-token", auto_error=False)

static_path = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_path), name="static")


async def _verify_token(api_key: str = Depends(_api_key_header)) -> str:
    if api_key != MAIA_KEY:
        raise HTTPException(status_code=403, detail="Clé MAIA invalide")
    return api_key

@app.post("/v1/compute")
async def compute(
    request: ComputeRequest,
    _token: str = Depends(_verify_token),
) -> str:
    
    save_message(request.session_id, "user", request.prompt)
    history = get_chat_history(request.session_id)
    messages = [{"role": "system", "content": "Tu es un assistant développeur."}] + history
    print(messages)
    url = "http://127.0.0.1:8080/v1/chat/completions"
    assistant_response = await run_inference(messages, url)
    
    if not assistant_response.startswith("[Erreur]"):
        save_message(request.session_id, "assistant", assistant_response)
        status_code = "success"
    else:
        status_code = "error"

    output_data = {
        "session_id": str(request.session_id),
        "content": str(assistant_response),
        "status": str(status_code)
    }

    try:
        ComputeResponse(**output_data)
    except ValidationError as e:
        print("❌ L'ERREUR DE VALIDATION EXACTE EST ICI :")
        print(e.json()) 
        
    return output_data

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/")
async def read_index():
    return FileResponse(os.path.join(static_path, "index.html"))