import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from src.client.services import maia
from src.client.services.database import init_db
from src.client.routers.chat import router as chat_router
from src.client.routers.workspace import router as workspace_router
from src.client.routers.metrics import router as metrics_router

static_path = os.path.join(os.path.dirname(__file__), "static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    await maia.start_client()
    print(f"Serveur d'inférence : {maia.SERVER_URL}")
    yield
    await maia.stop_client()


app = FastAPI(title="MAIA Client", lifespan=lifespan)

@app.get("/")
async def root():
    return FileResponse(os.path.join(static_path, "index.html"))

app.include_router(chat_router, prefix="/api")
app.include_router(workspace_router, prefix="/api")
app.include_router(metrics_router, prefix="/api")

app.mount("/static", StaticFiles(directory=static_path), name="static")
