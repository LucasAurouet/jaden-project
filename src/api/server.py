from fastapi import FastAPI
from contextlib import asynccontextmanager
from config import SERVER_NAME
from src.api.services.inference import start_client, stop_client
from src.api.routers.inference import router as inference_router
from src.api.routers.system import router as system_router
from src.api.routers.metrics import router as metrics_router

# Serveur d'inférence : une "coquille" devant les GPUs. Il authentifie,
# relaie vers llama-server et expose des métriques. Il ne stocke rien :
# historique, workspace et logique agentique vivent chez le client.

@asynccontextmanager
async def lifespan(app: FastAPI):
    await start_client()
    yield
    await stop_client()
    print("Fermeture du serveur")


# Pas de CORS : aucun navigateur n'appelle ce serveur directement, seulement
# des programmes (le client local, le CLI, une bibliothèque OpenAI...).
app = FastAPI(title="MAIA Inference Server", lifespan=lifespan)

@app.get("/")
async def root():
    return {"service": "maia-inference", "node": SERVER_NAME}

app.include_router(system_router, prefix="/v1")
app.include_router(inference_router, prefix="/v1")
app.include_router(metrics_router, prefix="/v1")
