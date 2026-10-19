import asyncio
import asyncpg
from pathlib import Path
from alembic import command
from alembic.config import Config as AlembicConfig
from pgvector.asyncpg import register_vector
from sqlalchemy.exc import SQLAlchemyError
from typing import Any, Dict, List, Tuple
from config import DATABASE_URL, EMBEDDING_DIM

ALEMBIC_INI = Path(__file__).resolve().parents[3] / "alembic.ini"

_pool: asyncpg.Pool | None = None


class DatabaseError(Exception):
    """Base injoignable ou incompatible avec la configuration."""


def _upgrade_schema():
    """Applique les migrations Alembic manquantes (alembic upgrade head)."""
    cfg = AlembicConfig(str(ALEMBIC_INI))
    cfg.attributes["embedded"] = True
    command.upgrade(cfg, "head")


async def init_db():
    global _pool
    try:
        # Dans un thread : env.py a sa propre boucle asyncio. Les migrations créent
        # l'extension vector, qui doit exister avant que le pool n'enregistre le type.
        await asyncio.to_thread(_upgrade_schema)
        _pool = await asyncpg.create_pool(DATABASE_URL, init=register_vector)
    except (OSError, asyncpg.PostgresError, SQLAlchemyError) as e:
        raise DatabaseError(f"Connexion à Postgres ou migration du schéma impossible ({e}).") from e

    # Pour vector, atttypmod vaut la dimension déclarée.
    dim = await _pool.fetchval("""
        SELECT atttypmod FROM pg_attribute
        WHERE attrelid = 'chunks'::regclass AND attname = 'embedding'
    """)
    if dim != EMBEDDING_DIM:
        raise DatabaseError(
            f"La table chunks stocke des vecteurs de dimension {dim}, mais EMBEDDING_DIM vaut "
            f"{EMBEDDING_DIM} : changer de modèle d'embedding impose de réindexer les documents."
        )


async def close_db():
    if _pool is not None:
        await _pool.close()


# ─── Conversations ──────────────────────────────────────────────────────────

async def save_exchange(session_id: str, prompt: str, answer: str):
    """Enregistre un tour complet (question + réponse) dans une seule transaction."""
    async with _pool.acquire() as conn, conn.transaction():
        await conn.execute("INSERT INTO sessions (id) VALUES ($1) ON CONFLICT DO NOTHING", session_id)
        await conn.executemany(
            "INSERT INTO messages (session_id, role, content) VALUES ($1, $2, $3)",
            [(session_id, "user", prompt), (session_id, "assistant", answer)],
        )


async def get_chat_context(session_id: str) -> Tuple[str | None, List[Dict[str, Any]]]:
    """
    Résumé de la session et messages qu'il ne couvre pas encore (avec leur id),
    du plus ancien au plus récent.
    """
    async with _pool.acquire() as conn, conn.transaction(isolation="repeatable_read", readonly=True):
        session = await conn.fetchrow(
            "SELECT summary, summary_upto FROM sessions WHERE id = $1", session_id
        )
        if session is None:
            return None, []
        rows = await conn.fetch(
            "SELECT id, role, content FROM messages WHERE session_id = $1 AND id > $2 ORDER BY id ASC",
            session_id, session["summary_upto"],
        )
    return session["summary"], [dict(row) for row in rows]


async def save_summary(session_id: str, summary: str, upto: int):
    """Avance le point de contrôle du résumé, sans jamais le faire reculer."""
    await _pool.execute(
        "UPDATE sessions SET summary = $2, summary_upto = $3 WHERE id = $1 AND summary_upto < $3",
        session_id, summary, upto,
    )


# ─── Documents (RAG) ────────────────────────────────────────────────────────

async def insert_document(source: str, chunks: List[str], embeddings: List[List[float]]) -> Dict[str, Any]:
    async with _pool.acquire() as conn, conn.transaction():
        row = await conn.fetchrow(
            "INSERT INTO documents (source) VALUES ($1) RETURNING id, source, created_at", source
        )
        await conn.executemany(
            "INSERT INTO chunks (document_id, position, content, embedding) VALUES ($1, $2, $3, $4)",
            [(row["id"], i, chunk, emb) for i, (chunk, emb) in enumerate(zip(chunks, embeddings))],
        )
    return {**dict(row), "chunks": len(chunks)}


async def list_documents() -> List[Dict[str, Any]]:
    rows = await _pool.fetch("""
        SELECT d.id, d.source, d.created_at, count(c.id) AS chunks
        FROM documents d LEFT JOIN chunks c ON c.document_id = d.id
        GROUP BY d.id ORDER BY d.id
    """)
    return [dict(row) for row in rows]


async def delete_document(document_id: int) -> bool:
    status = await _pool.execute("DELETE FROM documents WHERE id = $1", document_id)
    return status != "DELETE 0"


async def search_chunks(embedding: List[float], k: int) -> List[Dict[str, Any]]:
    """Les k passages les plus proches (distance cosinus), du plus au moins pertinent."""
    rows = await _pool.fetch("""
        SELECT c.id, d.source, c.content, 1 - (c.embedding <=> $1) AS score
        FROM chunks c JOIN documents d ON d.id = c.document_id
        ORDER BY c.embedding <=> $1
        LIMIT $2
    """, embedding, k)
    return [dict(row) for row in rows]


# Paramètres usuels de BM25 : saturation de la fréquence d'un terme (k1) et
# normalisation par la longueur du passage (b).
BM25_K1 = 1.2
BM25_B = 0.75


async def search_chunks_bm25(query: str, embedding: List[float], k: int) -> List[Dict[str, Any]]:
    """
    Les k meilleurs passages selon BM25, calculé sur le tsvector des passages
    (configuration french, comme dans la migration). Il suffit qu'un passage
    contienne un des termes de la requête : l'IDF donne leur poids aux termes rares.
    La longueur d'un passage est son nombre de lexèmes distincts (approximation).
    Le score cosinus est aussi renvoyé, pour les seuils appliqués après fusion.
    """
    rows = await _pool.fetch("""
        WITH terms AS (
            SELECT unnest(tsvector_to_array(to_tsvector('french', $1))) AS lexeme
        ),
        matched AS (
            -- plainto_tsquery relie les termes par & : on les relie par | (OU).
            SELECT c.id, c.tsv FROM chunks c
            WHERE c.tsv @@ replace(plainto_tsquery('french', $1)::text, ' & ', ' | ')::tsquery
        ),
        tf AS (
            SELECT m.id, t.lexeme, cardinality(t.positions) AS freq, length(m.tsv) AS len
            FROM matched m, unnest(m.tsv) t
            WHERE t.lexeme IN (SELECT lexeme FROM terms)
        ),
        df AS (
            SELECT lexeme, count(*) AS n FROM tf GROUP BY lexeme
        ),
        stats AS (
            SELECT count(*) AS total, avg(length(tsv)) AS avg_len FROM chunks
        ),
        ranked AS (
            SELECT tf.id, sum(
                ln(1 + (stats.total - df.n + 0.5) / (df.n + 0.5))
                * tf.freq * ($4 + 1) / (tf.freq + $4 * (1 - $5 + $5 * tf.len / stats.avg_len))
            ) AS bm25
            FROM tf JOIN df USING (lexeme) CROSS JOIN stats
            GROUP BY tf.id
            ORDER BY bm25 DESC
            LIMIT $3
        )
        SELECT c.id, d.source, c.content, 1 - (c.embedding <=> $2) AS score, r.bm25
        FROM ranked r JOIN chunks c ON c.id = r.id JOIN documents d ON d.id = c.document_id
        ORDER BY r.bm25 DESC
    """, query, embedding, k, BM25_K1, BM25_B)
    return [dict(row) for row in rows]
