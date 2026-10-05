import re
import httpx
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
