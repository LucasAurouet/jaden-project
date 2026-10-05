import httpx
from typing import List, Dict, Any
from config import SERVER_IP, SERVER_PORT, MAIA_KEY, LLM_TIMEOUT

SERVER_URL = f"http://{SERVER_IP}:{SERVER_PORT}"


class InferenceError(Exception):
    """Le serveur d'inférence n'a pas pu produire de réponse."""


# Client HTTP partagé vers le serveur d'inférence distant. La clé est ajoutée
# ici, côté Python : elle n'arrive jamais dans le navigateur.
_client: httpx.AsyncClient | None = None


async def start_client():
    global _client
    _client = httpx.AsyncClient(
        base_url=SERVER_URL,
        headers={"Authorization": f"Bearer {MAIA_KEY}"},
        timeout=httpx.Timeout(LLM_TIMEOUT + 10, connect=5.0),
    )


async def stop_client():
    if _client is not None:
        await _client.aclose()


async def chat_completion(messages: List[Dict[str, str]]) -> str:
    try:
        response = await _client.post("/v1/chat/completions", json={"messages": messages})
    except httpx.ConnectError as e:
        raise InferenceError(f"Serveur d'inférence injoignable ({SERVER_URL}).") from e
    except httpx.TimeoutException as e:
        raise InferenceError("Le serveur d'inférence a mis trop de temps à répondre.") from e

    if response.status_code == 401:
        raise InferenceError("Clé MAIA refusée par le serveur (vérifiez MAIA_KEY dans .env).")
    if response.status_code != 200:
        try:
            detail = response.json()["error"]["message"]
        except (ValueError, KeyError, TypeError):
            detail = response.text
        raise InferenceError(f"Erreur HTTP {response.status_code} : {detail}")

    try:
        return response.json()["choices"][0]["message"]["content"]
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
