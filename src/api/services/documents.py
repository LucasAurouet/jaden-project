import os
from pathlib import Path
from typing import Any, Dict, List
from src.api.services import database
from src.api.services.embeddings import embed

ALLOWED_EXTENSIONS = {".txt", ".md", ".py", ".js", ".json", ".html", ".css", ".csv", ".xml", ".ini", ".yaml", ".yml"}
MAX_UPLOAD_SIZE = 512 * 1024

# Taille des passages, en caractères (~300 à 400 tokens).
CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200


class DocumentError(Exception):
    """Document refusé (format, taille, contenu)."""


def chunk_text(text: str) -> List[str]:
    """
    Regroupe les paragraphes en passages d'au plus CHUNK_SIZE caractères.
    Un paragraphe trop long est découpé en fenêtres qui se chevauchent de
    CHUNK_OVERLAP caractères.
    """
    chunks: List[str] = []
    current = ""
    for paragraph in (p.strip() for p in text.split("\n\n")):
        if not paragraph:
            continue
        if len(paragraph) > CHUNK_SIZE:
            if current:
                chunks.append(current)
                current = ""
            step = CHUNK_SIZE - CHUNK_OVERLAP
            chunks.extend(paragraph[i:i + CHUNK_SIZE] for i in range(0, len(paragraph) - CHUNK_OVERLAP, step))
        elif current and len(current) + 2 + len(paragraph) > CHUNK_SIZE:
            chunks.append(current)
            current = paragraph
        else:
            current = f"{current}\n\n{paragraph}" if current else paragraph
    if current:
        chunks.append(current)
    return chunks


async def ingest(filename: str, content: bytes) -> Dict[str, Any]:
    """Découpe, vectorise et indexe un fichier texte envoyé par l'utilisateur."""
    name = os.path.basename(filename or "")
    if not name or name.startswith("."):
        raise DocumentError("Nom de fichier invalide.")
    if Path(name).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise DocumentError(
            f"Format non pris en charge. Formats autorisés : {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    if len(content) > MAX_UPLOAD_SIZE:
        raise DocumentError(f"Fichier trop volumineux (max {MAX_UPLOAD_SIZE // 1024} Ko).")

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    chunks = chunk_text(text)
    if not chunks:
        raise DocumentError("Le fichier est vide.")

    embeddings = await embed(chunks)
    return await database.insert_document(name, chunks, embeddings)
