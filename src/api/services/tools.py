import json
import asyncpg
from typing import Any, Awaitable, Callable, Dict, List
from config import RAG_MIN_SCORE, RAG_AUTO_MIN_SCORE
from src.api.services import database
from src.api.services.embeddings import embed, EmbeddingError

# Limites propres au contexte du modèle.
DEFAULT_SEARCH_RESULTS = 5
MAX_SEARCH_RESULTS = 10
AUTO_SEARCH_RESULTS = 3


def format_passages(results: List[Dict[str, Any]]) -> str:
    return "\n\n".join(
        f"[{i}] {r['source']} (score {r['score']:.2f})\n{r['content']}"
        for i, r in enumerate(results, 1)
    )


async def auto_search(query: str) -> List[Dict[str, Any]]:
    """
    Recherche automatique faite avant chaque réponse. Ne lève jamais : un
    fournisseur d'embeddings ou une base indisponible ne doit pas bloquer le chat.
    """
    try:
        [embedding] = await embed([query])
        candidates = await database.search_chunks(embedding, AUTO_SEARCH_RESULTS)
    except (EmbeddingError, OSError, asyncpg.PostgresError):
        return []
    return [r for r in candidates if r["score"] >= RAG_AUTO_MIN_SCORE]


# ─── Tools ──────────────────────────────────────────────────────────────────

async def search_documents(query: str, k: int = DEFAULT_SEARCH_RESULTS) -> str:
    k = max(1, min(int(k), MAX_SEARCH_RESULTS))
    [embedding] = await embed([query])
    candidates = await database.search_chunks(embedding, k)
    if not candidates:
        return "Aucun document indexé."
    results = [r for r in candidates if r["score"] >= RAG_MIN_SCORE]
    if not results:
        return (
            f"Aucun passage suffisamment pertinent (meilleur score {candidates[0]['score']:.2f}, "
            f"seuil {RAG_MIN_SCORE:.2f}). Reformule la requête ou réponds sans les documents."
        )
    return format_passages(results)


# ─── Registre ───────────────────────────────────────────────────────────────

# Chaque entrée : {"function": coroutine, "description": str, "parameters": JSON Schema}.
TOOLS: Dict[str, Dict[str, Any]] = {
    "search_documents": {
        "function": search_documents,
        "description": (
            "Recherche sémantique dans les documents fournis par l'utilisateur. "
            "Renvoie au plus k passages pertinents avec leur source : "
            "peut en renvoyer moins, voire aucun, si rien n'est assez proche."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Ce que l'on cherche, formulé en langage naturel."},
                "k": {
                    "type": "integer",
                    "description": f"Nombre de passages à renvoyer (défaut {DEFAULT_SEARCH_RESULTS}, max {MAX_SEARCH_RESULTS}).",
                },
            },
            "required": ["query"],
        },
    },
}

TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {"name": name, "description": t["description"], "parameters": t["parameters"]},
    }
    for name, t in TOOLS.items()
]


async def execute_tool(name: str, raw_arguments: str | Dict[str, Any] | None) -> str:
    """
    Exécute un tool demandé par le modèle. Ne lève jamais : toute erreur est
    renvoyée sous forme de texte pour que le modèle puisse corriger sa demande.
    """
    tool = TOOLS.get(name)
    if tool is None:
        return f"Erreur : tool inconnu '{name}'."

    # Les arguments sont normalement une chaîne JSON, mais certains
    # fournisseurs renvoient directement un objet.
    if isinstance(raw_arguments, dict):
        arguments = raw_arguments
    else:
        try:
            arguments = json.loads(raw_arguments or "{}")
        except json.JSONDecodeError:
            return f"Erreur : arguments JSON invalides pour '{name}'."

    func: Callable[..., Awaitable[str]] = tool["function"]
    try:
        return await func(**arguments)
    except (TypeError, ValueError) as e:
        return f"Erreur : arguments incorrects pour '{name}' ({e})."
    except EmbeddingError as e:
        return f"Erreur : {e}"
    except (OSError, asyncpg.PostgresError) as e:
        return f"Erreur de base de données : {e}"
