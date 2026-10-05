import os
from contextlib import asynccontextmanager
from typing import List, Dict, Any
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from src.client.services import maia
from src.client.services.chat import ChatService
from src.client.services.database import init_db
from src.client.services.file import FileService
from src.schemas import ComputeRequest, ComputeResponse

# Application locale du poste de travail : elle sert l'interface web,
# garde l'historique et le workspace, et délègue l'inférence au serveur GPU.

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


@app.post("/api/compute", response_model=ComputeResponse)
async def compute(request: ComputeRequest) -> ComputeResponse:
    return await ChatService.process_compute(
        session_id=request.session_id,
        prompt=request.prompt
    )


@app.post("/api/workspace/upload")
async def upload_file(
    file: UploadFile = File(...),
    session_id: str = Form(...),
) -> Dict[str, Any]:
    result = await FileService.feed_file_to_session(file, session_id)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return result


# Route synchrone (def) : FastAPI l'exécute dans un threadpool, le parcours
# du disque ne bloque donc pas la boucle asyncio.
@app.get("/api/workspace/inspect")
def list_files() -> List[Dict[str, Any]]:
    return FileService.list_workspace_files()["files"]


@app.get("/api/metrics")
async def metrics() -> Dict[str, Any]:
    # Relais vers le serveur GPU : le navigateur n'a pas besoin de la clé.
    return await maia.get_server_metrics()


app.mount("/static", StaticFiles(directory=static_path), name="static")
