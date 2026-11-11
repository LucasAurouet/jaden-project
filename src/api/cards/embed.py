"""
Vectorisation des cartes pour la recherche hybride (python main.py sync-cards).

Seules les cartes dont le texte à vectoriser a changé (ou qui n'ont pas encore
de vecteur) sont envoyées au fournisseur d'embeddings, par lots enregistrés au
fil de l'eau : une vectorisation interrompue reprend là où elle s'est arrêtée.
"""
import hashlib
from typing import Any, Callable, Dict, List

from config import EMBEDDING_PASSAGE_PREFIX
from src.api.services import database
from src.api.services.embeddings import embed

# Cartes vectorisées puis enregistrées à la fois.
WRITE_BATCH = 256


def card_text(card: Dict[str, Any]) -> str:
    """
    Texte vectorisé d'une carte : nom, ligne de type et effet. Les
    champs absents (race d'un Lien...) sont simplement omis.
    """
    typeline = " / ".join(
        part for part in (card["human_type"] or card["type"], card["race"], card["attribute"]) if part
    )
    return f"{card['name']}\n{typeline}\n{card['description']}"


def _hash(text: str) -> str:
    # Le préfixe fait partie de l'empreinte : le changer impose de revectoriser.
    return hashlib.sha256((EMBEDDING_PASSAGE_PREFIX + text).encode()).hexdigest()


async def embed_cards(reembed: bool = False, log: Callable[[str], None] = print) -> int:
    """
    Vectorise les cartes sans vecteur à jour (toutes si reembed, par exemple
    après un changement de modèle). Renvoie le nombre de cartes vectorisées.
    Lève EmbeddingError si le fournisseur est indisponible : les lots déjà
    enregistrés sont conservés.
    """
    pool = database.get_pool()
    rows = await pool.fetch("""
        SELECT id, name, type, raw->>'humanReadableCardType' AS human_type, race, attribute, description,
               embedding_hash
        FROM cards ORDER BY id
    """)
    pending: List[tuple] = []
    for row in rows:
        text = card_text(dict(row))
        digest = _hash(text)
        if reembed or row["embedding_hash"] != digest:
            pending.append((row["id"], text, digest))

    if not pending:
        log("Card vectors are up to date.")
        return 0

    log(f"Embedding {len(pending)} card(s)…")
    done = 0
    for start in range(0, len(pending), WRITE_BATCH):
        batch = pending[start:start + WRITE_BATCH]
        vectors = await embed([EMBEDDING_PASSAGE_PREFIX + text for _, text, _ in batch])
        await pool.executemany(
            "UPDATE cards SET embedding = $2, embedding_hash = $3 WHERE id = $1",
            [(card_id, vector, digest) for (card_id, _, digest), vector in zip(batch, vectors)],
        )
        done += len(batch)
        log(f"  {done}/{len(pending)}")
    return done
