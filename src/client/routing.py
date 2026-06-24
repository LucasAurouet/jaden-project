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
    Générateur asynchrone pur utilisant aiter_lines().
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
            data_buf = []

            async for line in response.aiter_lines():
                if line.startswith(":"):
                    continue

                if line.startswith("event:"):
                    raw_event = line.removeprefix("event:")
                    event_type = raw_event[1:] if raw_event.startswith(" ") else raw_event
                elif line.startswith("data:"):
                    raw_data = line.removeprefix("data:")
                    data_buf.append(raw_data[1:] if raw_data.startswith(" ") else raw_data)
                elif line == "":
                    full_data = "\n".join(data_buf)
                    for event in _dispatch(event_type, full_data, node_name):
                        yield event
                    
                    event_type = "text"
                    data_buf = []

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