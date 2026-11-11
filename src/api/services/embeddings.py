import httpx
from typing import Any, Dict, List
from config import EMBEDDING_BASE_URL, EMBEDDING_API_KEY, EMBEDDING_MODEL, EMBEDDING_DIM, LLM_TIMEOUT

# Textes envoyés par requête : reste sous les limites des API hébergées.
BATCH_SIZE = 32

_client: httpx.AsyncClient | None = None


async def start_client():
    global _client
    _client = httpx.AsyncClient(
        base_url=EMBEDDING_BASE_URL,
        headers={"Authorization": f"Bearer {EMBEDDING_API_KEY}"} if EMBEDDING_API_KEY else None,
        timeout=httpx.Timeout(LLM_TIMEOUT, connect=5.0),
    )


async def stop_client():
    if _client is not None:
        await _client.aclose()


class EmbeddingError(Exception):
    """Le fournisseur d'embeddings n'a pas pu vectoriser les textes."""


async def embed(texts: List[str]) -> List[List[float]]:
    """Vectorise les textes via /v1/embeddings, dans l'ordre d'entrée."""
    vectors: List[List[float]] = []
    for start in range(0, len(texts), BATCH_SIZE):
        vectors.extend(await _embed_batch(texts[start:start + BATCH_SIZE]))
    return vectors


async def _embed_batch(texts: List[str]) -> List[List[float]]:
    payload: Dict[str, Any] = {"input": texts}
    if EMBEDDING_MODEL:
        payload["model"] = EMBEDDING_MODEL

    try:
        response = await _client.post("/v1/embeddings", json=payload)
    except httpx.ConnectError as e:
        raise EmbeddingError("The embedding provider is unreachable.") from e
    except httpx.TimeoutException as e:
        raise EmbeddingError("The embedding provider did not answer in time.") from e

    if response.status_code != 200:
        raise EmbeddingError(f"HTTP error {response.status_code} from the embedding provider: {response.text}")

    try:
        data = sorted(response.json()["data"], key=lambda d: d["index"])
        vectors = [d["embedding"] for d in data]
    except (ValueError, KeyError, TypeError) as e:
        raise EmbeddingError("The embedding provider's answer is not in the expected format.") from e

    if len(vectors) != len(texts) or any(len(v) != EMBEDDING_DIM for v in vectors):
        raise EmbeddingError(
            f"Unexpected embeddings: {EMBEDDING_DIM} dimensions expected (EMBEDDING_DIM), "
            f"the model returns {len(vectors[0]) if vectors else 0}."
        )
    return vectors
