import json
import asyncio
from typing import Any, Callable, Dict, List

# ─── Registre ───────────────────────────────────────────────────────────────

# Chaque entrée : {"function": callable, "description": str, "parameters": JSON Schema}.
# Vide pour l'instant : les futurs tools (recherche RAG...) se déclarent ici.
TOOLS: Dict[str, Dict[str, Any]] = {}

TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {"name": name, "description": t["description"], "parameters": t["parameters"]},
    }
    for name, t in TOOLS.items()
]


async def execute_tool(name: str, raw_arguments: str) -> str:
    """
    Exécute un tool demandé par le modèle. Ne lève jamais : toute erreur est
    renvoyée sous forme de texte pour que le modèle puisse corriger sa demande.
    """
    tool = TOOLS.get(name)
    if tool is None:
        return f"Erreur : tool inconnu '{name}'."

    try:
        arguments = json.loads(raw_arguments or "{}")
    except json.JSONDecodeError:
        return f"Erreur : arguments JSON invalides pour '{name}'."

    func: Callable[..., str] = tool["function"]
    try:
        return await asyncio.to_thread(func, **arguments)
    except TypeError as e:
        return f"Erreur : arguments incorrects pour '{name}' ({e})."
    except OSError as e:
        return f"Erreur système : {e}"
