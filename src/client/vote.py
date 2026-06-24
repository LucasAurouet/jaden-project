from src.schemas import ExpertResponse
from src.core.inference import generate, stream_inference
from typing import AsyncIterator
from src.schemas import TextEvent, ErrorEvent


def _build_voting_prompt(original_prompt: str, responses: list[ExpertResponse]) -> str:
    context = "\n".join(
        f"--- AVIS DE L'EXPERT [{r.node} / {r.expert}] ---\n{r.response}"
        for r in responses
    )
    return (
        "Tu es l'arbitre du système MAIA. Synthétise les réponses des experts "
        "pour répondre au prompt initial.\n"
        "Élimine les hallucinations, garde la rigueur technique et fusionne le tout "
        "de manière fluide.\n\n"
        f"PROMPT INITIAL : {original_prompt}\n\n"
        f"{context}"
    )


async def vote_best_answer(
    original_prompt: str,
    responses: list[ExpertResponse],
) -> AsyncIterator[str]:
    prompt = _build_voting_prompt(original_prompt, responses)
    try:
        async for event in stream_inference(prompt, "writing"):
            if event["type"] == "text":
                yield TextEvent(node="VOTE_ARBITRE", content=event["data"])
    except Exception as e:
        yield ErrorEvent(node="VOTE_ARBITRE", error=f"Erreur critique : {e}")
    