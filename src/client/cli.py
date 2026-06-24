"""
Consommateur terminal de l'orchestrateur.
Responsabilité unique : traduire les événements en affichage terminal.
"""

from src.client.client_app import run_query
from src.client import display
from src.schemas import PerfSummary


async def start_cli() -> None:
    display.print_banner()

    while True:
        try:
            prompt = input("\nMAIA App > ").strip()
            if prompt.lower() == "q":
                break
            if not prompt:
                continue

            display.print_routing_start()
            perf_summaries: list[PerfSummary] = []

            async for event in run_query(prompt):
                if event.type == "text":
                    if event.node == "SYSTEM":
                        display.print_routing_end()
                    elif event.node == "VOTE":
                        display.stream_text(event.content, "VOTE")
                    else:
                        display.stream_text(event.content, event.node)

                elif event.type == "metrics":
                    if "t_s" in event.data:
                        perf_summaries.append(PerfSummary(**event.data))

                elif event.type == "error":
                    display.print_stream_error(event.node, "?", event.error)

            print()
            display.print_perf_table(perf_summaries)

        except KeyboardInterrupt:
            break