"""
Responsabilité unique : toutes les interactions avec l'API Ollama locale.
Ni FastAPI, ni logique métier, ni affichage.
"""

import json
import time
from typing import AsyncIterator, TypedDict

import httpx

from config import OLLAMA_URL, OLLAMA_MODEL, NODE_NAME
from src.core.experts import get_system_prompt
from src.core.metrics import parse_ollama_metrics


class TextChunk(TypedDict):
    type: str   # "text"
    data: str


class MetricsChunk(TypedDict):
    type: str   # "metrics"
    data: dict


InferenceEvent = TextChunk | MetricsChunk


async def stream_inference(
    prompt: str,
    expert_type: str,
) -> AsyncIterator[InferenceEvent]:
    """
    Générateur asynchrone : yield des TextChunk pendant l'inférence,
    puis un unique MetricsChunk à la fin.

    Lève une exception si Ollama est indisponible.
    """
    system_prompt = get_system_prompt(expert_type)
    payload = {
        "model":  OLLAMA_MODEL,
        "prompt": prompt,
        "system": system_prompt,
        "stream": True,
    }

    t0 = time.time()
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream(
            "POST", f"{OLLAMA_URL}/api/generate", json=payload, timeout=None
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                if not chunk.get("done", False):
                    yield {"type": "text", "data": chunk.get("response", "")}
                else:
                    metrics = parse_ollama_metrics(chunk, NODE_NAME, expert_type, t0)
                    yield {"type": "metrics", "data": metrics}


async def generate(prompt: str) -> str:
    """
    Appel Ollama non-streamé. Utilisé par le service de vote.
    """
    async with httpx.AsyncClient(timeout=None) as client:
        res = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=None,
        )
        res.raise_for_status()
        return res.json().get("response", "")