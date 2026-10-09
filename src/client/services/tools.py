import json
import asyncio
from typing import Any, Callable, Dict, List
from src.client.services import workspace
from src.client.services.workspace import WorkspaceError

# Limites propres au contexte du modèle (le service, lui, renvoie tout).
MAX_READ_CHARS = 20_000
MAX_SEARCH_RESULTS = 50


# ─── Adaptateurs workspace ──────────────────────────────────────────────────

def list_dir(path: str = ".") -> str:
    entries = workspace.list_dir(path)
    if not entries:
        return "(dossier vide)"
    return "\n".join(f"{e.name}/" if e.is_dir() else e.name for e in entries)


def read_file(path: str) -> str:
    content = workspace.read_text(path)
    if len(content) > MAX_READ_CHARS:
        content = content[:MAX_READ_CHARS] + f"\n... (fichier tronqué à {MAX_READ_CHARS} caractères)"
    return content


def search(pattern: str, path: str = ".") -> str:
    results = []
    for file_path, lineno, line in workspace.search(pattern, path):
        if len(results) >= MAX_SEARCH_RESULTS:
            results.append(f"... (limité à {MAX_SEARCH_RESULTS} résultats)")
            break
        results.append(f"{file_path}:{lineno}: {line.strip()}")
    return "\n".join(results) if results else "Aucun résultat."


# ─── Registre ───────────────────────────────────────────────────────────────

_PATH_PARAM = {"type": "string", "description": "Chemin relatif à la racine du workspace."}

TOOLS: Dict[str, Dict[str, Any]] = {
    "list_dir": {
        "function": list_dir,
        "description": "Liste le contenu d'un dossier du workspace.",
        "parameters": {
            "type": "object",
            "properties": {"path": _PATH_PARAM},
            "required": [],
        },
    },
    "read_file": {
        "function": read_file,
        "description": "Lit le contenu d'un fichier texte du workspace.",
        "parameters": {
            "type": "object",
            "properties": {"path": _PATH_PARAM},
            "required": ["path"],
        },
    },
    "search": {
        "function": search,
        "description": "Recherche une expression régulière dans les fichiers du workspace (façon grep).",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Expression régulière Python."},
                "path": {**_PATH_PARAM, "description": "Dossier où chercher (défaut : racine)."},
            },
            "required": ["pattern"],
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
    except WorkspaceError as e:
        return f"Erreur : {e}"
    except TypeError as e:
        return f"Erreur : arguments incorrects pour '{name}' ({e})."
    except OSError as e:
        return f"Erreur système : {e}"
