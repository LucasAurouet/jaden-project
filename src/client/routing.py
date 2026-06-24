"""
Responsabilité unique : ouvrir un stream SSE vers un peer et émettre des
événements typés. Zéro print, zéro logique métier.
Parser SSE minimal sur httpx brut — pas de dépendance httpx-sse.
"""

import json
from typing import AsyncIterator

import httpx

from config import MAIA_KEY
from src.schemas import TextEvent, MetricsEvent, ErrorEvent

StreamEvent = TextEvent | MetricsEvent | ErrorEvent


async def route_to_peer(
    client: httpx.AsyncClient,
    url: str,
    prompt: str,
    expert_type: str,
    node_name: str,
) -> AsyncIterator[StreamEvent]:
    """
    Générateur asynchrone pur.
    Yield : TextEvent | MetricsEvent | ErrorEvent
    """
    payload = {"prompt": prompt, "expert_type": expert_type}
    headers = {"maia-token": MAIA_KEY}

    try:
        async with client.stream(
            "POST",
            f"http://{url}/v1/compute",
            json=payload,
            headers=headers,
            timeout=None,
        ) as response:
            response.raise_for_status()

            event_type = "text"
            data_buf = ""

            async for line in response.aiter_lines():
                if line.startswith("event:"):
                    event_type = line.removeprefix("event:").strip()
                elif line.startswith("data:"):
                    data_buf = line.removeprefix("data:").strip()
                elif line == "":  # ligne vide = événement complet
                    for event in _dispatch(event_type, data_buf, node_name):
                        yield event
                    event_type = "text"
                    data_buf = ""

    except Exception as e:
        yield ErrorEvent(node=node_name, error=str(e))


def _dispatch(event_type: str, data: str, node_name: str) -> list[StreamEvent]:
    if event_type == "text":
        return [TextEvent(node=node_name, content=data)]
    if event_type == "metrics":
        try:
            return [MetricsEvent(node=node_name, data=json.loads(data))]
        except json.JSONDecodeError:
            return []
    if event_type == "error":
        return [ErrorEvent(node=node_name, error=data)]
    return []