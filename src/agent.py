import os
from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
import httpx
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title=f"MAIA Agent - {os.getenv('MAIA_NODE_NAME')}")

API_KEY_NAME = "X-MAIA-Token"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

# Modèle de données strict pour l'API
class ComputeRequest(BaseModel):
    prompt: str
    expert_type: str

async def verify_token(api_key: str = Depends(api_key_header)):
    if api_key != os.getenv("MAIA_SECRET_KEY"):
        raise HTTPException(status_code=403, detail="Clé MAIA invalide")
    return api_key

@app.post("/v1/compute")
async def process_compute(request: ComputeRequest, token: str = Depends(verify_token)):
    # Cartographie des LoRA / Prompts systèmes
    expert_registry = {
        "code": "Tu es un ingénieur logiciel senior. Donne des réponses techniques et du code optimisé.",
        "maths": "Tu es un mathématicien. Résous le problème de manière analytique et étape par étape.",
        "writing": "Tu es un rédacteur professionnel. Rédige avec un style élégant, clair et percutant."
    }
    
    system_prompt = expert_registry.get(request.expert_type, "Tu es un assistant IA généraliste.")
    
    # Appel asynchrone à l'Ollama local (fermé au réseau mondial)
    async with httpx.AsyncClient() as client:
        try:
            ollama_payload = {
                "model": "llama3:8b",
                "prompt": request.prompt,
                "system": system_prompt,
                "stream": False
            }
            response = await client.post(
                f"{os.getenv('OLLAMA_BASE_URL')}/api/generate", 
                json=ollama_payload, 
                timeout=60.0
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=500, detail="Échec de l'inférence Ollama")
                
            return {
                "node": os.getenv("MAIA_NODE_NAME"),
                "expert": request.expert_type,
                "response": response.json().get("response")
            }
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Ollama indisponible : {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))