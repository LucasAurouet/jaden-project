import asyncio
from typing import AsyncIterator

import httpx

from config import PEERS_IP, NODE_NAME
from src.core.experts import assign_expert
from src.core.metrics import to_perf_summary
from src.client.routing import route_to_peer
from src.client.vote import vote_best_answer
from src.schemas import ExpertResponse, PerfSummary, TextEvent, MetricsEvent, ErrorEvent


async def _consume_peer(
    client: httpx.AsyncClient,
    url: str,
    peer_index: int,
    prompt: str,
    valid_responses: list[ExpertResponse],
    perf_summaries: list[PerfSummary],
    queue: asyncio.Queue,
) -> None:
    expert_type = assign_expert(peer_index)
    full_text = ""

    async for event in route_to_peer(client, url, prompt, expert_type, NODE_NAME):
        await queue.put(event)
        if event.type == "text":
            full_text += event.content
        elif event.type == "metrics":
            perf = event.data.get("performance", event.data)
            summary = to_perf_summary(
                {"node": event.data.get("node", NODE_NAME), "performance": perf},
                expert_type,
            )
            perf_summaries.append(summary)
        elif event.type == "error":
            return

    if full_text:
        valid_responses.append(
            ExpertResponse(node=NODE_NAME, expert=expert_type, response=full_text)
        )


async def run_query(prompt: str) -> AsyncIterator[TextEvent | MetricsEvent | ErrorEvent]:
    async with httpx.AsyncClient(timeout=None) as client:
        valid_responses: list[ExpertResponse] = []
        perf_summaries: list[PerfSummary] = []
        queue: asyncio.Queue = asyncio.Queue()

        tasks = [
            asyncio.create_task(
                _consume_peer(client, url, i, prompt, valid_responses, perf_summaries, queue)
            )
            for i, url in enumerate(PEERS_IP)
        ]

        while tasks:
            done = [t for t in tasks if t.done()]
            for t in done:
                tasks.remove(t)
            while not queue.empty():
                yield await queue.get()
            if tasks:
                await asyncio.sleep(0.01)

        while not queue.empty():
            yield await queue.get()

        yield TextEvent(node="SYSTEM", content="\n\n---PEERS_DONE---\n\n")

        if not valid_responses:
            return
        
        async for event in vote_best_answer(prompt, valid_responses):
            if event.type == "metrics":
                perf = event.data.get("performance", event.data)
                summary = to_perf_summary({"node": "VOTE", "performance": perf}, "writing")
                perf_summaries.append(summary)
            yield event

        for summary in perf_summaries:
            yield MetricsEvent(node=summary.node, data=summary.dict())