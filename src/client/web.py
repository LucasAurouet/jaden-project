import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from src.client.services import jaden
from src.client.routers.auth import router as auth_router
from src.client.routers.chat import router as chat_router
from src.client.routers.sessions import router as sessions_router
from src.client.routers.metrics import router as metrics_router

static_path = os.path.join(os.path.dirname(__file__), "static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await jaden.start_client()
    print(f"Inference server: {jaden.SERVER_URL}")
    yield
    await jaden.stop_client()


app = FastAPI(title="Jaden Client", lifespan=lifespan)

@app.get("/")
async def root():
    return FileResponse(os.path.join(static_path, "index.html"))

app.include_router(auth_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(sessions_router, prefix="/api")
app.include_router(metrics_router, prefix="/api")

app.mount("/static", StaticFiles(directory=static_path), name="static")
