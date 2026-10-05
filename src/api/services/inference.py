import re
import httpx
from config import LLM_BASE_URL, LLM_TIMEOUT
from src.schemas import LlamaMetrics

# Un seul client pour toute la durée de vie du serveur : les connexions TCP
# vers llama-server sont réutilisées au lieu d'être rouvertes à chaque requête.
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


def get_client() -> httpx.AsyncClient:
    return _client


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
