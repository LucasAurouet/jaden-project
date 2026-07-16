import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from src.api.services.database import init_db
from src.api.routers.chat import router as chat_router
from src.api.routers.workspace import router as workspace_router
from src.api.routers.system import router as system_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    print("Base de données SQLite initialisée avec succès.")
    
    yield
    
    print("Fermeture du serveur")


app = FastAPI(title="MAIA Server", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system_router)
app.include_router(chat_router, prefix="/v1")
app.include_router(workspace_router, prefix="/v1")

static_path = os.path.join(os.path.dirname(__file__), "../", "client/","static")
app.mount("/static", StaticFiles(directory=static_path), name="static")
