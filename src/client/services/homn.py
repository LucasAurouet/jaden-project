import httpx
from typing import Dict, Any
from config import SERVER_IP, SERVER_PORT, HOMN_KEY, LLM_TIMEOUT
from src.schemas import ComputeRequest, ComputeResponse

SERVER_URL = f"http://{SERVER_IP}:{SERVER_PORT}"


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


async def compute(session_id: str, prompt: str) -> ComputeResponse:
    """Transmet la requête à l'agent du serveur. Toute erreur est renvoyée en status="error"."""
    def error(message: str) -> ComputeResponse:
        return ComputeResponse(session_id=session_id, content=message, status="error")

    payload = ComputeRequest(session_id=session_id, prompt=prompt).model_dump()
    try:
        response = await _client.post("/v1/compute", json=payload)
    except httpx.ConnectError:
        return error(f"Serveur d'inférence injoignable ({SERVER_URL}).")
    except httpx.TimeoutException:
        return error("Le serveur d'inférence a mis trop de temps à répondre.")

    if response.status_code == 401:
        return error("Clé Homn refusée par le serveur (vérifiez HOMN_KEY dans .env).")
    if response.status_code != 200:
        try:
            detail = response.json()["error"]["message"]
        except (ValueError, KeyError, TypeError):
            detail = response.text
        return error(f"Erreur HTTP {response.status_code} : {detail}")

    try:
        return ComputeResponse.model_validate(response.json())
    except ValueError:
        return error("La réponse du serveur n'est pas au format attendu.")


async def get_server_metrics() -> Dict[str, Any]:
    try:
        response = await _client.get("/v1/metrics/all", timeout=2.0)
        if response.status_code == 200:
            return response.json()
    except httpx.HTTPError:
        pass
    return {}
