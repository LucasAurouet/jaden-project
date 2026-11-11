import json
import asyncpg
from typing import Any, Awaitable, Callable, Dict, List
from config import RAG_MIN_SCORE
from src.api.services import rag
from src.api.services.embeddings import EmbeddingError

# Limites propres au contexte du modèle.
DEFAULT_SEARCH_RESULTS = 5
MAX_SEARCH_RESULTS = 10


# ─── Tools ──────────────────────────────────────────────────────────────────

async def search_documents(_user_id: int, query: str, k: int = DEFAULT_SEARCH_RESULTS) -> str:
    k = max(1, min(int(k), MAX_SEARCH_RESULTS))
    candidates = await rag.search(query, k)
    if not candidates:
        return "No indexed document."
    # Un passage trouvé par mots-clés (BM25) est gardé même sous le seuil cosinus :
    # c'est le cas typique d'un identifiant ou d'un nom propre que les embeddings ratent.
    results = [r for r in candidates if r["score"] >= RAG_MIN_SCORE or r.get("bm25") is not None]
    if not results:
        best = max(r["score"] for r in candidates)
        return (
            f"No passage relevant enough (best score {best:.2f}, "
            f"threshold {RAG_MIN_SCORE:.2f}). Rephrase the query or answer without the documents."
        )
    return rag.format_passages(results)


# ─── Registre ───────────────────────────────────────────────────────────────

# Chaque entrée : {"function": coroutine, "description": str, "parameters": JSON Schema}.
# La coroutine reçoit en premier argument l'id de l'utilisateur (absent du schéma).
TOOLS: Dict[str, Dict[str, Any]] = {
    "search_documents": {
        "function": search_documents,
        "description": (
            "Search the reference documents (rules, guides) by meaning "
            "and by keywords (proper names, identifiers, exact terms). "
            "Returns at most k relevant passages with their source: "
            "may return fewer, or none, if nothing is close enough."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to look for, in natural language (English)."},
                "k": {
                    "type": "integer",
                    "description": f"Number of passages to return (default {DEFAULT_SEARCH_RESULTS}, max {MAX_SEARCH_RESULTS}).",
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


async def execute_tool(name: str, raw_arguments: str | Dict[str, Any] | None, user_id: int) -> str:
    """
    Exécute un tool demandé par le modèle. Ne lève jamais : toute erreur est
    renvoyée sous forme de texte pour que le modèle puisse corriger sa demande.
    """
    tool = TOOLS.get(name)
    if tool is None:
        return f"Error: unknown tool '{name}'."

    # Les arguments sont normalement une chaîne JSON, mais certains
    # fournisseurs renvoient directement un objet.
    if isinstance(raw_arguments, dict):
        arguments = raw_arguments
    else:
        try:
            arguments = json.loads(raw_arguments or "{}")
        except json.JSONDecodeError:
            return f"Error: invalid JSON arguments for '{name}'."

    if not isinstance(arguments, dict):
        return f"Error: the arguments of '{name}' must be a JSON object."
    # user_id vient du serveur, jamais du modèle.
    arguments.pop("user_id", None)

    func: Callable[..., Awaitable[str]] = tool["function"]
    try:
        return await func(user_id, **arguments)
    except (TypeError, ValueError) as e:
        return f"Error: wrong arguments for '{name}' ({e})."
    except EmbeddingError as e:
        return f"Error: {e}"
    except (OSError, asyncpg.PostgresError) as e:
        return f"Database error: {e}"
