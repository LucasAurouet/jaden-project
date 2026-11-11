import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from src.client.services import jaden
from src.client.routers.auth import router as auth_router
from src.client.routers.chat import router as chat_router
from src.client.routers.sessions import router as sessions_router
from src.client.routers.status import router as status_router

static_path = os.path.join(os.path.dirname(__file__), "static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await jaden.start_client()
    print(f"Inference server: {jaden.SERVER_URL}")
    yield
    await jaden.stop_client()


app = FastAPI(title="Jaden Client", lifespan=lifespan)


# Sans Cache-Control, le navigateur peut garder une ancienne version du front
# (app.js, style.css) après une mise à jour. no-cache le force à revalider à
# chaque chargement : le fichier n'est renvoyé que s'il a changé (sinon 304).
@app.middleware("http")
async def revalidate_front(request, call_next):
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/")
async def root():
    return FileResponse(os.path.join(static_path, "index.html"))

app.include_router(auth_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(sessions_router, prefix="/api")
app.include_router(status_router, prefix="/api")

app.mount("/static", StaticFiles(directory=static_path), name="static")
