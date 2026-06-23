import os
from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
import httpx
import uvicorn
from dotenv import load_dotenv
import psutil
import time

load_dotenv()

app = FastAPI(title="MAIA Agent Node")

API_KEY_NAME = "maia-token"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)
NODE_NAME = os.getenv("NODE_NAME")
NODE_PORT = os.getenv("NODE_PORT", 8000)
MAIA_KEY = os.getenv("MAIA_KEY")
OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://localhost:11434')

class ComputeRequest(BaseModel):
    prompt: str
    expert_type: str

async def verify_token(api_key: str = Depends(api_key_header)):
    if api_key != MAIA_KEY:
        raise HTTPException(status_code=403, detail="Clé MAIA invalide")
    return api_key

@app.post("/v1/compute")
async def process_compute(request: ComputeRequest, token: str = Depends(verify_token)):
    expert_registry = {
        "code": "Tu es un ingénieur logiciel senior. Donne du code optimisé.",
        "maths": "Tu es un mathématicien. Résous le problème étape par étape.",
        "writing": "Tu es un rédacteur professionnel. Rédige de manière claire."
    }
    system_prompt = expert_registry.get(request.expert_type, "Tu es un assistant généraliste.")
    
    t0 = time.time()
    async with httpx.AsyncClient() as client:
        try:
            ollama_payload = {
                "model": "llama3.2:3b",
                "prompt": request.prompt,
                "system": system_prompt,
                "stream": False
            }

            response = await client.post(
                f"{OLLAMA_URL}/api/generate", 
                json=ollama_payload, 
                timeout=None
            )

            ollama_output = response.json()

            httpx_time = time.time() - t0

            return {
                "node": NODE_NAME,
                "expert": request.expert_type,
                "response": ollama_output.get("response"),
                "performance": {
                    "tokens_sec": round(ollama_output.get("eval_count", 0) / (ollama_output.get("eval_duration", 0) / 1e9), 2),
                    "token_count": ollama_output.get("eval_count", 0),
                    "total_time": round(ollama_output.get("total_duration", 0) / 1e9, 2),
                    "loading_time": round(ollama_output.get("load_duration", 0) / 1e9, 2),
                    "ttft": round(ollama_output.get("prompt_eval_duration", 0) / 1e9, 2),
                    "eval_time": round(ollama_output.get("eval_duration", 0) / 1e9, 2),
                    "network_overhead": round(max(0, httpx_time - ollama_output.get("total_duration", 0)), 2),
                    "cpu_usage": psutil.cpu_percent(interval=None),
                    "ram_usage": psutil.virtual_memory().percent
                    }
            }
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Ollama local indisponible ({error_name})")

def start_agent():
    port = int(NODE_PORT)
    print(f"[Agent] Démarrage du noeud [{NODE_NAME}] sur le port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)