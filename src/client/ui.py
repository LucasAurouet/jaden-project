import gradio as gr
import pandas as pd

from src.client.client_app import run_query
from src.schemas import PerfSummary


async def chat(message: str, history: list):
    peers_output: dict[str, str] = {} 
    vote_output = ""
    perf_summaries: list[PerfSummary] = []
    in_vote = False

    async for event in run_query(message):

        if event.type == "text":
            if event.node == "SYSTEM":
                in_vote = True
                continue
            if in_vote:
                vote_output += event.content
                yield vote_output, _render_table(perf_summaries)
            else:
                peers_output[event.node] = peers_output.get(event.node, "") + event.content

                combined = "\n\n---\n\n".join(
                    f"**[{node}]**\n{text}"
                    for node, text in peers_output.items()
                )
                yield combined, _render_table(perf_summaries)

        elif event.type == "metrics":
            if "t_s" in event.data:
                perf_summaries.append(PerfSummary(**event.data))
                yield vote_output or "\n\n---\n\n".join(
                    f"**[{node}]**\n{text}" for node, text in peers_output.items()
                ), _render_table(perf_summaries)

        elif event.type == "error":
            yield f"[{event.node}] {event.error}", _render_table(perf_summaries)


def _render_table(summaries: list[PerfSummary]) -> pd.DataFrame | None:
    if not summaries:
        return None
    return pd.DataFrame([s.dict() for s in summaries])


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="MAIA") as demo:
        gr.Markdown("# M.A.I.A.")
        gr.Markdown("*Multi-Agent Inference Architecture*")

        with gr.Row():
            with gr.Column(scale=3):
                output = gr.Markdown(label="Réponse")
                msg = gr.Textbox(
                    placeholder="Posez votre question...",
                    label="",
                    lines=2,
                )
                send = gr.Button("Envoyer", variant="primary")

            with gr.Column(scale=1):
                table = gr.DataFrame(label="Métriques des noeuds", wrap=True)

        send.click(chat, inputs=[msg, gr.State([])], outputs=[output, table])
        msg.submit(chat, inputs=[msg, gr.State([])], outputs=[output, table])

    return demo


def start_ui():
    ui = build_ui()
    ui.launch(server_name="0.0.0.0", server_port=7860, theme=gr.themes.Soft())