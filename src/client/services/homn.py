import httpx
from typing import Any, Dict, List
from config import SERVER_IP, SERVER_PORT, HOMN_KEY, LLM_TIMEOUT
from src.schemas import ComputeRequest

SERVER_URL = f"http://{SERVER_IP}:{SERVER_PORT}"

# L'indexation vectorise chaque passage du document : bien plus long qu'une requête.
UPLOAD_TIMEOUT = 600.0


_client: httpx.AsyncClient | None = None


async def start_client():
    global _client
    _client = httpx.AsyncClient(
        base_url=SERVER_URL,
        headers={"Authorization": f"Bearer {HOMN_KEY}"},
        timeout=httpx.Timeout(LLM_TIMEOUT + 10, connect=5.0),
    )


async def stop_client():
    if _client is not None:
        await _client.aclose()


class ServerError(Exception):
    """Requête refusée ou impossible ; status est le code HTTP à renvoyer au navigateur."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


async def _request(method: str, path: str, stream: bool = False, **kwargs) -> httpx.Response:
    """
    Requête authentifiée vers le serveur ; lève ServerError si elle n'aboutit pas.
    Avec stream=True, le corps reste à lire et la réponse à fermer par l'appelant.
    """
    request = _client.build_request(method, path, **kwargs)
    try:
        response = await _client.send(request, stream=stream)
    except httpx.ConnectError as e:
        raise ServerError(502, f"Serveur d'inférence injoignable ({SERVER_URL}).") from e
    except httpx.TimeoutException as e:
        raise ServerError(504, "Le serveur d'inférence a mis trop de temps à répondre.") from e

    if response.is_error:
        await response.aread()
        await response.aclose()
    if response.status_code == 401:
        raise ServerError(502, "Clé Homn refusée par le serveur (vérifiez HOMN_KEY dans .env).")
    if response.is_error:
        try:
            body = response.json()
            detail = body.get("detail") or body["error"]["message"]
        except (ValueError, KeyError, TypeError, AttributeError):
            detail = response.text
        raise ServerError(response.status_code, str(detail))
    return response


async def compute(session_id: str, prompt: str) -> httpx.Response:
    """Ouvre le flux SSE de l'agent du serveur (voir ChatService.stream_compute)."""
    payload = ComputeRequest(session_id=session_id, prompt=prompt).model_dump()
    return await _request("POST", "/v1/compute", stream=True, json=payload)


async def upload_document(filename: str, content: bytes, content_type: str | None) -> Dict[str, Any]:
    response = await _request(
        "POST", "/v1/documents",
        files={"file": (filename, content, content_type or "application/octet-stream")},
        timeout=UPLOAD_TIMEOUT,
    )
    return response.json()


async def list_documents() -> List[Dict[str, Any]]:
    return (await _request("GET", "/v1/documents")).json()


async def delete_document(document_id: int):
    await _request("DELETE", f"/v1/documents/{document_id}")


async def get_server_metrics() -> Dict[str, Any]:
    try:
        response = await _client.get("/v1/metrics/all", timeout=2.0)
        if response.status_code == 200:
            return response.json()
    except httpx.HTTPError:
        pass
    return {}
