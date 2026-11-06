import httpx
from urllib.parse import quote
from typing import Any, Dict, List
from config import SERVER_IP, SERVER_PORT, LLM_TIMEOUT
from src.schemas import ComputeRequest, LoginRequest

SERVER_URL = f"http://{SERVER_IP}:{SERVER_PORT}"

# L'indexation vectorise chaque passage du document : bien plus long qu'une requête.
UPLOAD_TIMEOUT = 600.0


_client: httpx.AsyncClient | None = None


async def start_client():
    global _client
    _client = httpx.AsyncClient(
        base_url=SERVER_URL,
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


async def _request(method: str, path: str, token: str | None, stream: bool = False, **kwargs) -> httpx.Response:
    """
    Requête vers le serveur, avec le jeton de connexion de l'utilisateur ; lève
    ServerError si elle n'aboutit pas (un 401 signifie qu'il faut se reconnecter).
    Avec stream=True, le corps reste à lire et la réponse à fermer par l'appelant.
    """
    if token is not None:
        kwargs["headers"] = {**kwargs.get("headers", {}), "Authorization": f"Bearer {token}"}
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
        try:
            body = response.json()
            detail = body.get("detail") or body["error"]["message"]
        except (ValueError, KeyError, TypeError, AttributeError):
            detail = response.text
        raise ServerError(response.status_code, str(detail))
    return response


# ─── Authentification ───────────────────────────────────────────────────────

async def login(username: str, password: str) -> Dict[str, Any]:
    payload = LoginRequest(username=username, password=password).model_dump()
    return (await _request("POST", "/v1/auth/login", None, json=payload)).json()


async def logout(token: str):
    await _request("POST", "/v1/auth/logout", token)


async def me(token: str) -> Dict[str, Any]:
    return (await _request("GET", "/v1/auth/me", token)).json()


# ─── Conversations ──────────────────────────────────────────────────────────

async def compute(token: str, session_id: str, prompt: str) -> httpx.Response:
    """Ouvre le flux SSE de l'agent du serveur (voir ChatService.stream_compute)."""
    payload = ComputeRequest(session_id=session_id, prompt=prompt).model_dump()
    return await _request("POST", "/v1/compute", token, stream=True, json=payload)


async def list_sessions(token: str) -> List[Dict[str, Any]]:
    return (await _request("GET", "/v1/sessions", token)).json()


async def get_messages(token: str, session_id: str) -> List[Dict[str, Any]]:
    return (await _request("GET", f"/v1/sessions/{quote(session_id, safe='')}/messages", token)).json()


async def delete_session(token: str, session_id: str):
    await _request("DELETE", f"/v1/sessions/{quote(session_id, safe='')}", token)


# ─── Documents ──────────────────────────────────────────────────────────────

async def upload_document(token: str, filename: str, content: bytes, content_type: str | None, shared: bool) -> Dict[str, Any]:
    response = await _request(
        "POST", "/v1/documents", token,
        files={"file": (filename, content, content_type or "application/octet-stream")},
        data={"shared": "true" if shared else "false"},
        timeout=UPLOAD_TIMEOUT,
    )
    return response.json()


async def list_documents(token: str) -> List[Dict[str, Any]]:
    return (await _request("GET", "/v1/documents", token)).json()


async def delete_document(token: str, document_id: int):
    await _request("DELETE", f"/v1/documents/{document_id}", token)


async def get_server_metrics(token: str) -> Dict[str, Any]:
    try:
        response = await _client.get("/v1/metrics/all", headers={"Authorization": f"Bearer {token}"}, timeout=2.0)
        if response.status_code == 200:
            return response.json()
    except httpx.HTTPError:
        pass
    return {}
