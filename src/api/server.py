from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from config import SERVER_NAME
from src.api.services import embeddings
from src.api.services.database import init_db, close_db
from src.api.services.inference import start_client, stop_client, UpstreamUnavailable, UpstreamTimeout
from src.api.routers.inference import router as inference_router
from src.api.routers.auth import router as auth_router
from src.api.routers.chat import router as chat_router
from src.api.routers.sessions import router as sessions_router
from src.api.routers.system import router as system_router
from src.api.routers.metrics import router as metrics_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await start_client()
    await embeddings.start_client()
    yield
    await embeddings.stop_client()
    await stop_client()
    await close_db()
    print("Server shutting down")

app = FastAPI(title="Jaden Inference Server", lifespan=lifespan)


def _error(status: int, message: str, kind: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"message": message, "type": kind}})

@app.exception_handler(UpstreamUnavailable)
async def upstream_unavailable(request: Request, exc: UpstreamUnavailable):
    return _error(502, "The inference engine is unreachable.", "upstream_unavailable")

@app.exception_handler(UpstreamTimeout)
async def upstream_timeout(request: Request, exc: UpstreamTimeout):
    return _error(504, "The inference engine did not answer in time.", "upstream_timeout")


@app.get("/")
async def root():
    return {"service": "jaden-inference", "node": SERVER_NAME}

app.include_router(system_router, prefix="/v1")
app.include_router(inference_router, prefix="/v1")
app.include_router(auth_router, prefix="/v1")
app.include_router(chat_router, prefix="/v1")
app.include_router(sessions_router, prefix="/v1")
app.include_router(metrics_router, prefix="/v1")
