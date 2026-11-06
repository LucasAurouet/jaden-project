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

async def search_documents(user_id: int, query: str, k: int = DEFAULT_SEARCH_RESULTS) -> str:
    k = max(1, min(int(k), MAX_SEARCH_RESULTS))
    candidates = await rag.search(query, k, user_id)
    if not candidates:
        return "Aucun document indexé."
    # Un passage trouvé par mots-clés (BM25) est gardé même sous le seuil cosinus :
    # c'est le cas typique d'un identifiant ou d'un nom propre que les embeddings ratent.
    results = [r for r in candidates if r["score"] >= RAG_MIN_SCORE or r.get("bm25") is not None]
    if not results:
        best = max(r["score"] for r in candidates)
        return (
            f"Aucun passage suffisamment pertinent (meilleur score {best:.2f}, "
            f"seuil {RAG_MIN_SCORE:.2f}). Reformule la requête ou réponds sans les documents."
        )
    return rag.format_passages(results)


# ─── Registre ───────────────────────────────────────────────────────────────

# Chaque entrée : {"function": coroutine, "description": str, "parameters": JSON Schema}.
# La coroutine reçoit en premier argument l'id de l'utilisateur (absent du schéma).
TOOLS: Dict[str, Dict[str, Any]] = {
    "search_documents": {
        "function": search_documents,
        "description": (
            "Recherche dans les documents fournis par l'utilisateur, par le sens "
            "et par mots-clés (noms propres, identifiants, termes exacts). "
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


async def execute_tool(name: str, raw_arguments: str | Dict[str, Any] | None, user_id: int) -> str:
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

    if not isinstance(arguments, dict):
        return f"Erreur : les arguments de '{name}' doivent être un objet JSON."
    # user_id vient du serveur, jamais du modèle.
    arguments.pop("user_id", None)

    func: Callable[..., Awaitable[str]] = tool["function"]
    try:
        return await func(user_id, **arguments)
    except (TypeError, ValueError) as e:
        return f"Erreur : arguments incorrects pour '{name}' ({e})."
    except EmbeddingError as e:
        return f"Erreur : {e}"
    except (OSError, asyncpg.PostgresError) as e:
        return f"Erreur de base de données : {e}"
