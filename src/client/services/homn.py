import httpx
from typing import List, Dict, Any
from config import SERVER_IP, SERVER_PORT, HOMN_KEY, LLM_TIMEOUT

SERVER_URL = f"http://{SERVER_IP}:{SERVER_PORT}"


class InferenceError(Exception):
    """Le serveur d'inférence n'a pas pu produire de réponse."""


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


async def chat_completion(
    messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    """Renvoie le message assistant complet (content et éventuels tool_calls)."""
    payload: Dict[str, Any] = {"messages": messages}
    if tools:
        payload["tools"] = tools

    try:
        response = await _client.post("/v1/chat/completions", json=payload)
    except httpx.ConnectError as e:
        raise InferenceError(f"Serveur d'inférence injoignable ({SERVER_URL}).") from e
    except httpx.TimeoutException as e:
        raise InferenceError("Le serveur d'inférence a mis trop de temps à répondre.") from e

    if response.status_code == 401:
        raise InferenceError("Clé Homn refusée par le serveur (vérifiez HOMN_KEY dans .env).")
    if response.status_code != 200:
        try:
            detail = response.json()["error"]["message"]
        except (ValueError, KeyError, TypeError):
            detail = response.text
        raise InferenceError(f"Erreur HTTP {response.status_code} : {detail}")

    try:
        return response.json()["choices"][0]["message"]
    except (ValueError, KeyError, IndexError) as e:
        raise InferenceError("La réponse du serveur n'est pas au format attendu.") from e


async def get_server_metrics() -> Dict[str, Any]:
    try:
        response = await _client.get("/v1/metrics/all", timeout=2.0)
        if response.status_code == 200:
            return response.json()
    except httpx.HTTPError:
        pass
    return {}
