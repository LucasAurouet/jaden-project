"""
Responsabilité unique : ouvrir un stream HTTP vers un peer et émettre des
événements typés. Zéro print, zéro logique métier.
"""

import json
from typing import AsyncIterator

import httpx

from config import MAIA_KEY
from src.core.metrics import STREAM_SEPARATOR
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
            async for chunk in response.aiter_text():
                if not chunk:
                    continue
                yield from _parse_chunk(chunk, node_name)

    except Exception as e:
        yield ErrorEvent(node=node_name, error=str(e))


def _parse_chunk(chunk: str, node_name: str) -> list[StreamEvent]:
    """
    Parse un chunk brut du stream MAIA.
    Le protocole : texte normal OU  |||{json}|||  en fin de stream.
    """
    events: list[StreamEvent] = []

    if STREAM_SEPARATOR not in chunk:
        events.append(TextEvent(node=node_name, content=chunk))
        return events

    parts = chunk.split(STREAM_SEPARATOR)
    # parts = [texte_avant, json_metrics, texte_après (vide en pratique)]
    if parts[0].strip():
        events.append(TextEvent(node=node_name, content=parts[0]))

    if len(parts) >= 2 and parts[1].strip():
        try:
            data = json.loads(parts[1])
            events.append(MetricsEvent(node=node_name, data=data))
        except json.JSONDecodeError:
            pass  # chunk corrompu : on ignore silencieusement

    return events