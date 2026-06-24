"""
Responsabilité unique : orchestrer les tâches concurrentes et déléguer
l'affichage à display.py et la logique à routing/vote.
"""

import asyncio

import httpx

from config import PEERS_IP, NODE_NAME
from src.core.experts import assign_expert
from src.core.metrics import to_perf_summary
from src.client.routing import route_to_peer
from src.client.vote import vote_best_answer
from src.client import display
from src.schemas import ExpertResponse, PerfSummary


async def _consume_peer(
    client: httpx.AsyncClient,
    url: str,
    peer_index: int,
    prompt: str,
    valid_responses: list[ExpertResponse],
    perf_summaries: list[PerfSummary],
) -> None:
    expert_type = assign_expert(peer_index)
    full_text = ""

    async for event in route_to_peer(client, url, prompt, expert_type, NODE_NAME):
        if event.type == "text":
            display.stream_text(event.content, url)
            full_text += event.content

        elif event.type == "metrics":
            perf = event.data.get("performance", event.data)
            summary = to_perf_summary({"node": event.data.get("node", NODE_NAME), "performance": perf}, expert_type)
            perf_summaries.append(summary)

        elif event.type == "error":
            display.print_stream_error(NODE_NAME, expert_type, event.error)
            return

    if full_text:
        valid_responses.append(
            ExpertResponse(node=NODE_NAME, expert=expert_type, response=full_text)
        )


async def start() -> None:
    display.print_banner()

    async with httpx.AsyncClient(timeout=None) as client:
        while True:
            try:
                prompt = input("\nMAIA App > ").strip()
                if prompt.lower() == "q":
                    break
                if not prompt:
                    continue

                display.print_routing_start()

                valid_responses: list[ExpertResponse] = []
                perf_summaries: list[PerfSummary] = []

                tasks = [
                    _consume_peer(client, url, i, prompt, valid_responses, perf_summaries)
                    for i, url in enumerate(PEERS_IP)
                ]
                await asyncio.gather(*tasks)

                display.print_routing_end()
                display.print_perf_table(perf_summaries)

                if valid_responses:
                    async for chunk in vote_best_answer(prompt, valid_responses):
                        display.stream_text(chunk, "VOTE")

            except KeyboardInterrupt:
                break