import os
import re
import json
import asyncio
from pathlib import Path
from typing import Any, Callable, Dict, List
from src.client.services.file import WORKSPACE_DIR, IGNORE_DIRS, IGNORE_FILES, IGNORE_EXTENSIONS

WORKSPACE_ROOT = Path(WORKSPACE_DIR).resolve()
MAX_READ_CHARS = 20_000
MAX_SEARCH_RESULTS = 50


class ToolError(Exception):
    """Erreur renvoyée au modèle sous forme de résultat de tool."""


def _resolve(path: str) -> Path:
    """Résout un chemin relatif au workspace et refuse toute sortie de celui-ci."""
    target = (WORKSPACE_ROOT / path.lstrip("/")).resolve()
    if not target.is_relative_to(WORKSPACE_ROOT):
        raise ToolError(f"Accès refusé : '{path}' est en dehors du workspace.")
    return target


def _is_visible(entry: Path) -> bool:
    if entry.name.startswith("."):
        return False
    if entry.is_dir():
        return entry.name not in IGNORE_DIRS
    return entry.name not in IGNORE_FILES and entry.suffix.lower() not in IGNORE_EXTENSIONS


def _relative(path: Path) -> str:
    return path.relative_to(WORKSPACE_ROOT).as_posix() or "."


# ─── Implémentations ────────────────────────────────────────────────────────

def list_dir(path: str = ".") -> str:
    target = _resolve(path)
    if not target.is_dir():
        raise ToolError(f"'{path}' n'est pas un dossier.")

    entries = sorted(
        (e for e in target.iterdir() if _is_visible(e)),
        key=lambda e: (not e.is_dir(), e.name),
    )
    if not entries:
        return "(dossier vide)"
    return "\n".join(f"{e.name}/" if e.is_dir() else e.name for e in entries)


def read_file(path: str) -> str:
    target = _resolve(path)
    if not target.is_file():
        raise ToolError(f"'{path}' n'existe pas ou n'est pas un fichier.")

    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise ToolError(f"'{path}' n'est pas un fichier texte UTF-8.")

    if len(content) > MAX_READ_CHARS:
        content = content[:MAX_READ_CHARS] + f"\n... (fichier tronqué à {MAX_READ_CHARS} caractères)"
    return content


def search(pattern: str, path: str = ".") -> str:
    try:
        regex = re.compile(pattern)
    except re.error as e:
        raise ToolError(f"Expression régulière invalide : {e}")

    root = _resolve(path)
    results = []

    for current, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if _is_visible(Path(current) / d))
        for name in sorted(files):
            file_path = Path(current) / name
            if not _is_visible(file_path):
                continue
            try:
                lines = file_path.read_text(encoding="utf-8").splitlines()
            except (UnicodeDecodeError, OSError):
                continue
            for lineno, line in enumerate(lines, 1):
                if regex.search(line):
                    results.append(f"{_relative(file_path)}:{lineno}: {line.strip()}")
                    if len(results) >= MAX_SEARCH_RESULTS:
                        results.append(f"... (limité à {MAX_SEARCH_RESULTS} résultats)")
                        return "\n".join(results)

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
    except ToolError as e:
        return f"Erreur : {e}"
    except TypeError as e:
        return f"Erreur : arguments incorrects pour '{name}' ({e})."
    except OSError as e:
        return f"Erreur système : {e}"
