import os
import asyncio
import asyncpg
import hashlib
from pathlib import Path
from typing import Any, Dict, List
from config import EMBEDDING_PASSAGE_PREFIX, EMBEDDING_QUERY_PREFIX, RAG_AUTO_MIN_SCORE, RAG_HYBRID_SEARCH
from src.api.services import database
from src.api.services.embeddings import embed, EmbeddingError

ALLOWED_EXTENSIONS = {".txt", ".md", ".py", ".js", ".json", ".html", ".css", ".csv", ".xml", ".ini", ".yaml", ".yml"}
MAX_UPLOAD_SIZE = 512 * 1024

# Taille des passages, en caractères (~300 à 400 tokens).
CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200

# Passages joints automatiquement à chaque message.
AUTO_SEARCH_RESULTS = 3

# Recherche hybride : nombre de candidats demandés à chaque recherche (vectorielle
# et BM25) avant fusion, et constante de la Reciprocal Rank Fusion (60 d'usage).
MIN_CANDIDATES = 20
RRF_K = 60


class DocumentError(Exception):
    """Document refusé (format, taille, contenu)."""


class DuplicateDocument(DocumentError):
    """Fichier au contenu identique à un document déjà indexé."""


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

    # Vérifié avant les embeddings, pour ne pas les calculer pour rien. Seul le
    # contenu compte : deux fichiers de même nom mais différents sont gardés.
    sha256 = hashlib.sha256(content).hexdigest()
    existing = await database.find_document_by_hash(sha256)
    if existing:
        raise DuplicateDocument(f"Ce fichier est déjà indexé (sous le nom {existing['source']}).")

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    chunks = chunk_text(text)
    if not chunks:
        raise DocumentError("Le fichier est vide.")

    # Le préfixe ne sert qu'au vecteur : content (affichage, BM25) reste le texte brut.
    embeddings = await embed([EMBEDDING_PASSAGE_PREFIX + chunk for chunk in chunks])
    try:
        return await database.insert_document(name, sha256, chunks, embeddings)
    except asyncpg.UniqueViolationError:
        # Même fichier envoyé deux fois en même temps : l'index unique tranche.
        raise DuplicateDocument("Ce fichier est déjà indexé.")


# ─── Recherche ──────────────────────────────────────────────────────────────

def _fuse(*rankings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Reciprocal Rank Fusion : chaque classement donne 1 / (RRF_K + rang) à ses
    passages. Seuls les rangs comptent, pas les scores (cosinus et BM25 ne sont
    pas comparables). Un passage trouvé par les deux recherches remonte en tête.
    """
    fused: Dict[int, Dict[str, Any]] = {}
    for ranking in rankings:
        for rank, result in enumerate(ranking, 1):
            entry = fused.setdefault(result["id"], {"bm25": None, **result, "rrf": 0.0})
            entry["rrf"] += 1 / (RRF_K + rank)
            if result.get("bm25") is not None:
                entry["bm25"] = result["bm25"]
    return sorted(fused.values(), key=lambda r: r["rrf"], reverse=True)


async def search(query: str, k: int) -> List[Dict[str, Any]]:
    """
    Les k passages les plus pertinents, du plus au moins pertinent. En mode
    hybride, fusionne la recherche vectorielle et BM25 (mots-clés : noms propres,
    identifiants, termes rares que les embeddings rapprochent mal). Chaque
    passage a son score cosinus (score) et, s'il a été trouvé par BM25, bm25.
    """
    [embedding] = await embed([EMBEDDING_QUERY_PREFIX + query])
    if not RAG_HYBRID_SEARCH:
        return await database.search_chunks(embedding, k)
    n = max(4 * k, MIN_CANDIDATES)
    vector, lexical = await asyncio.gather(
        database.search_chunks(embedding, n),
        database.search_chunks_bm25(query, embedding, n),
    )
    return _fuse(vector, lexical)[:k]


async def auto_search(query: str) -> List[Dict[str, Any]]:
    """
    Recherche automatique faite avant chaque réponse. Ne lève jamais : un
    fournisseur d'embeddings ou une base indisponible ne doit pas bloquer le chat.
    Faute de modèle pour juger de la pertinence, seul le score cosinus compte :
    BM25 élargit les candidats et influe sur leur ordre, sans exempter du seuil.
    """
    try:
        candidates = await search(query, MIN_CANDIDATES)
    except (EmbeddingError, OSError, asyncpg.PostgresError):
        return []
    return [r for r in candidates if r["score"] >= RAG_AUTO_MIN_SCORE][:AUTO_SEARCH_RESULTS]


def format_passages(results: List[Dict[str, Any]]) -> str:
    return "\n\n".join(
        f"[{i}] {r['source']} (score {r['score']:.2f}"
        + (f", BM25 {r['bm25']:.1f}" if r.get("bm25") is not None else "")
        + f")\n{r['content']}"
        for i, r in enumerate(results, 1)
    )
