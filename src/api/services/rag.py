import os
import asyncpg
from pathlib import Path
from typing import Any, Dict, List
from config import RAG_AUTO_MIN_SCORE
from src.api.services import database
from src.api.services.embeddings import embed, EmbeddingError

ALLOWED_EXTENSIONS = {".txt", ".md", ".py", ".js", ".json", ".html", ".css", ".csv", ".xml", ".ini", ".yaml", ".yml"}
MAX_UPLOAD_SIZE = 512 * 1024

# Taille des passages, en caractères (~300 à 400 tokens).
CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200

# Passages joints automatiquement à chaque message.
AUTO_SEARCH_RESULTS = 3


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


# ─── Recherche ──────────────────────────────────────────────────────────────

async def search(query: str, k: int) -> List[Dict[str, Any]]:
    """Les k passages les plus proches de la requête, du plus au moins pertinent."""
    [embedding] = await embed([query])
    return await database.search_chunks(embedding, k)


async def auto_search(query: str) -> List[Dict[str, Any]]:
    """
    Recherche automatique faite avant chaque réponse. Ne lève jamais : un
    fournisseur d'embeddings ou une base indisponible ne doit pas bloquer le chat.
    """
    try:
        candidates = await search(query, AUTO_SEARCH_RESULTS)
    except (EmbeddingError, OSError, asyncpg.PostgresError):
        return []
    return [r for r in candidates if r["score"] >= RAG_AUTO_MIN_SCORE]


def format_passages(results: List[Dict[str, Any]]) -> str:
    return "\n\n".join(
        f"[{i}] {r['source']} (score {r['score']:.2f})\n{r['content']}"
        for i, r in enumerate(results, 1)
    )
