import asyncpg
from pgvector.asyncpg import register_vector
from typing import Any, Dict, List
from config import DATABASE_URL, EMBEDDING_DIM

_pool: asyncpg.Pool | None = None


class DatabaseError(Exception):
    """Base injoignable ou incompatible avec la configuration."""


async def init_db():
    global _pool
    try:
        # L'extension doit exister avant que le pool n'enregistre le type vector.
        conn = await asyncpg.connect(DATABASE_URL)
    except (OSError, asyncpg.PostgresError) as e:
        raise DatabaseError(f"Connexion à Postgres impossible ({e}).") from e
    try:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    finally:
        await conn.close()

    _pool = await asyncpg.create_pool(DATABASE_URL, init=register_vector)

    async with _pool.acquire() as conn, conn.transaction():
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT DEFAULT 'Nouvelle discussion',
                created_at TIMESTAMPTZ DEFAULT now()
            )
        """)

        # Uniquement les tours de conversation (user / assistant).
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id BIGSERIAL PRIMARY KEY,
                session_id TEXT REFERENCES sessions(id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT now()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id BIGSERIAL PRIMARY KEY,
                source TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT now()
            )
        """)

        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS chunks (
                id BIGSERIAL PRIMARY KEY,
                document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                position INT NOT NULL,
                content TEXT NOT NULL,
                embedding vector({EMBEDDING_DIM}) NOT NULL
            )
        """)
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops)"
        )

        # Pour vector, atttypmod vaut la dimension déclarée.
        dim = await conn.fetchval("""
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


async def get_chat_history(session_id: str) -> List[Dict[str, str]]:
    """Récupère l'historique complet d'une session sous forme utilisable par le LLM."""
    rows = await _pool.fetch(
        "SELECT role, content FROM messages WHERE session_id = $1 ORDER BY id ASC",
        session_id,
    )
    return [{"role": row["role"], "content": row["content"]} for row in rows]


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
        SELECT d.source, c.content, 1 - (c.embedding <=> $1) AS score
        FROM chunks c JOIN documents d ON d.id = c.document_id
        ORDER BY c.embedding <=> $1
        LIMIT $2
    """, embedding, k)
    return [dict(row) for row in rows]
