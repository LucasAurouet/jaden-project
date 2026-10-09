import os
import re
from pathlib import Path
from typing import Any, Dict, Iterator, List, Tuple
from config import WORKSPACE_DIR

WORKSPACE_ROOT: Path = WORKSPACE_DIR

# Dossier (relatif au workspace) où sont déposés les fichiers envoyés depuis l'UI.
UPLOAD_DIR = "uploads"
ALLOWED_UPLOAD_EXTENSIONS = {".txt", ".md", ".py", ".js", ".json", ".html", ".css", ".csv", ".xml", ".ini", ".yaml", ".yml"}
MAX_UPLOAD_SIZE = 512 * 1024

IGNORE_DIRS = {
    "venv", ".venv", "env", ".env",
    "__pycache__", ".git", "node_modules",
    ".vscode", ".idea", "dist", "build"
}
IGNORE_FILES = {
    ".DS_Store", "desktop.ini", "thumbs.db"
}
IGNORE_EXTENSIONS = {
    ".pyc", ".pyo", ".pyd",
}


class WorkspaceError(Exception):
    """Opération refusée ou impossible sur le workspace."""


class WorkspaceUnavailable(WorkspaceError):
    """Le dossier racine du workspace n'existe pas."""


# ─── Chemins & filtrage ─────────────────────────────────────────────────────

def resolve(path: str) -> Path:
    """Résout un chemin relatif au workspace et refuse toute sortie de celui-ci."""
    if not WORKSPACE_ROOT.is_dir():
        raise WorkspaceUnavailable(f"Workspace introuvable : {WORKSPACE_ROOT}")

    target = (WORKSPACE_ROOT / path.lstrip("/")).resolve()
    if not target.is_relative_to(WORKSPACE_ROOT):
        raise WorkspaceError(f"Accès refusé : '{path}' est en dehors du workspace.")
    return target


def relative(path: Path) -> str:
    return path.relative_to(WORKSPACE_ROOT).as_posix() or "."


def is_visible(entry: Path) -> bool:
    # Les liens symboliques sont ignorés : ils pourraient pointer hors du
    # workspace ou créer des boucles lors des parcours récursifs.
    if entry.name.startswith(".") or entry.is_symlink():
        return False
    if entry.is_dir():
        return entry.name not in IGNORE_DIRS
    return entry.name not in IGNORE_FILES and entry.suffix.lower() not in IGNORE_EXTENSIONS


def _visible_children(directory: Path) -> List[Path]:
    """Entrées visibles d'un dossier : sous-dossiers d'abord, puis fichiers, par ordre alphabétique."""
    try:
        entries = list(directory.iterdir())
    except OSError:
        return []
    return sorted((e for e in entries if is_visible(e)), key=lambda e: (not e.is_dir(), e.name))


def _walk(directory: Path) -> Iterator[Path]:
    for entry in _visible_children(directory):
        if entry.is_dir():
            yield from _walk(entry)
        else:
            yield entry


# ─── Lecture ────────────────────────────────────────────────────────────────

def list_dir(path: str = ".") -> List[Path]:
    target = resolve(path)
    if not target.is_dir():
        raise WorkspaceError(f"'{path}' n'est pas un dossier.")
    return _visible_children(target)


def list_files() -> List[Dict[str, Any]]:
    """Liste plate de tous les fichiers visibles, avec leurs métadonnées."""
    files = []
    for file_path in _walk(resolve(".")):
        try:
            stat = file_path.stat()
        except OSError:
            continue
        files.append({"name": relative(file_path), "size": stat.st_size, "modified": stat.st_mtime})
    return files


def tree() -> str:
    """Arborescence ASCII du workspace (dossiers suffixés par '/')."""
    lines = ["/ (workspace)"]

    def build(directory: Path, prefix: str):
        children = _visible_children(directory)
        for i, entry in enumerate(children):
            is_last = i == len(children) - 1
            connector = "└── " if is_last else "├── "
            if entry.is_dir():
                lines.append(f"{prefix}{connector}{entry.name}/")
                build(entry, prefix + ("    " if is_last else "│   "))
            else:
                lines.append(f"{prefix}{connector}{entry.name}")

    build(resolve("."), "")
    return "\n".join(lines)


def read_text(path: str) -> str:
    target = resolve(path)
    if not target.is_file():
        raise WorkspaceError(f"'{path}' n'existe pas ou n'est pas un fichier.")
    try:
        return target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise WorkspaceError(f"'{path}' n'est pas un fichier texte UTF-8.")


def search(pattern: str, path: str = ".") -> Iterator[Tuple[str, int, str]]:
    """Recherche une regex ligne par ligne. Produit (chemin relatif, n° de ligne, ligne)."""
    try:
        regex = re.compile(pattern)
    except re.error as e:
        raise WorkspaceError(f"Expression régulière invalide : {e}")

    for file_path in _walk(resolve(path)):
        try:
            lines = file_path.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(lines, 1):
            if regex.search(line):
                yield relative(file_path), lineno, line


# ─── Écriture ───────────────────────────────────────────────────────────────

def save_upload(filename: str, content: bytes) -> str:
    """
    Dépose un fichier texte envoyé par l'utilisateur dans UPLOAD_DIR, converti
    en UTF-8 (remplace un éventuel fichier du même nom). Renvoie son chemin
    relatif au workspace.
    """
    name = os.path.basename(filename or "")
    if not name or name.startswith("."):
        raise WorkspaceError("Nom de fichier invalide.")

    if Path(name).suffix.lower() not in ALLOWED_UPLOAD_EXTENSIONS:
        raise WorkspaceError(
            f"Format non pris en charge. Formats autorisés : {', '.join(sorted(ALLOWED_UPLOAD_EXTENSIONS))}"
        )
    if len(content) > MAX_UPLOAD_SIZE:
        raise WorkspaceError(f"Fichier trop volumineux (max {MAX_UPLOAD_SIZE // 1024} Ko).")

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    target = resolve(f"{UPLOAD_DIR}/{name}")
    target.parent.mkdir(exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return relative(target)
