import re
import httpx
from typing import Any, Dict, List
from config import LLM_BASE_URL, LLM_TIMEOUT
from src.schemas import LlamaMetrics

_client: httpx.AsyncClient | None = None


async def start_client():
    global _client
    _client = httpx.AsyncClient(
        base_url=LLM_BASE_URL,
        timeout=httpx.Timeout(LLM_TIMEOUT, connect=5.0),
    )


async def stop_client():
    if _client is not None:
        await _client.aclose()


class UpstreamUnavailable(Exception):
    """llama-server ne répond pas (arrêté, mauvais port...)."""


class UpstreamTimeout(Exception):
    """llama-server n'a pas répondu dans le délai imparti."""


async def forward(method: str, path: str, body: bytes | None = None) -> httpx.Response:
    request = _client.build_request(
        method, path, content=body, headers={"Content-Type": "application/json"}
    )
    try:
        return await _client.send(request, stream=True)
    except httpx.ConnectError as e:
        raise UpstreamUnavailable() from e
    except httpx.TimeoutException as e:
        raise UpstreamTimeout() from e


class InferenceError(Exception):
    """Le moteur d'inférence n'a pas pu produire de réponse exploitable."""


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
        raise InferenceError("Le moteur d'inférence (llama-server) est injoignable.") from e
    except httpx.TimeoutException as e:
        raise InferenceError("Le moteur d'inférence n'a pas répondu à temps.") from e

    if response.status_code != 200:
        try:
            detail = response.json()["error"]["message"]
        except (ValueError, KeyError, TypeError):
            detail = response.text
        raise InferenceError(f"Erreur HTTP {response.status_code} : {detail}")

    try:
        return response.json()["choices"][0]["message"]
    except (ValueError, KeyError, IndexError) as e:
        raise InferenceError("La réponse du moteur d'inférence n'est pas au format attendu.") from e


async def get_llama_metrics_from_api() -> LlamaMetrics:
    """Lit l'endpoint Prometheus /metrics de llama-server (lancé avec --metrics)."""
    try:
        r = await _client.get("/metrics", timeout=1.0)
        if r.status_code != 200:
            return LlamaMetrics()
    except httpx.HTTPError:
        return LlamaMetrics()

    text = r.text

    def extract(key: str) -> float | None:
        m = re.search(rf"^{re.escape(key)}\s+(\S+)", text, re.MULTILINE)
        return float(m.group(1)) if m else None

    return LlamaMetrics(
        tg_tokens_per_sec=extract("llamacpp:predicted_tokens_seconds"),
        pp_tokens_per_sec=extract("llamacpp:prompt_tokens_seconds"),
        kv_cache_usage=extract("llamacpp:kv_cache_usage_ratio"),
    )
