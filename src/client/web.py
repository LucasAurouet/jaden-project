import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from src.client.services import homn
from src.client.routers.chat import router as chat_router
from src.client.routers.documents import router as documents_router
from src.client.routers.metrics import router as metrics_router

static_path = os.path.join(os.path.dirname(__file__), "static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await homn.start_client()
    print(f"Serveur d'inférence : {homn.SERVER_URL}")
    yield
    await homn.stop_client()


app = FastAPI(title="Homn Systems Client", lifespan=lifespan)

@app.get("/")
async def root():
    return FileResponse(os.path.join(static_path, "index.html"))

app.include_router(chat_router, prefix="/api")
app.include_router(documents_router, prefix="/api")
app.include_router(metrics_router, prefix="/api")

app.mount("/static", StaticFiles(directory=static_path), name="static")
