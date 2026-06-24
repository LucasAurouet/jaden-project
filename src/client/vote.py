"""
Responsabilité unique : construire le prompt de vote et appeler l'inférence.
Aucun appel httpx direct — on passe par core.inference.
"""

from src.schemas import ExpertResponse
from src.core.inference import generate, stream_inference


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
) -> str:
    prompt = _build_voting_prompt(original_prompt, responses)
    try:
        return await stream_inference(prompt, "writing")
    except Exception as e:
        return f"Erreur critique du service de vote : {type(e).__name__} : {e}"