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


def get_pool() -> asyncpg.Pool:
    """Pool de connexions, pour les modules qui ont leurs propres requêtes (cards/)."""
    if _pool is None:
        raise DatabaseError("Base non initialisée : appeler init_db d'abord.")
    return _pool


async def close_db():
    if _pool is not None:
        await _pool.close()


# ─── Utilisateurs ───────────────────────────────────────────────────────────

USER_COLUMNS = "u.id, u.username, u.is_admin, u.created_at"


async def create_user(username: str, password_hash: str, is_admin: bool) -> Dict[str, Any]:
    """Crée un compte (asyncpg.UniqueViolationError si le nom est pris)."""
    row = await _pool.fetchrow(
        "INSERT INTO users AS u (username, password_hash, is_admin) VALUES ($1, $2, $3) "
        f"RETURNING {USER_COLUMNS}",
        username, password_hash, is_admin,
    )
    return dict(row)


async def get_user_credentials(username: str) -> Dict[str, Any] | None:
    row = await _pool.fetchrow(
        f"SELECT {USER_COLUMNS}, u.password_hash FROM users u WHERE u.username = $1", username
    )
    return dict(row) if row else None


async def set_password(username: str, password_hash: str) -> bool:
    """Change le mot de passe et révoque tous les jetons du compte."""
    async with _pool.acquire() as conn, conn.transaction():
        user_id = await conn.fetchval(
            "UPDATE users SET password_hash = $2 WHERE username = $1 RETURNING id", username, password_hash
        )
        if user_id is None:
            return False
        await conn.execute("DELETE FROM auth_tokens WHERE user_id = $1", user_id)
    return True


async def delete_user(username: str) -> bool:
    """Supprime le compte avec ses jetons et ses sessions."""
    status = await _pool.execute("DELETE FROM users WHERE username = $1", username)
    return status != "DELETE 0"


async def create_token(user_id: int, token_hash: str, ttl_days: int):
    """Enregistre un jeton, et purge au passage les jetons expirés."""
    async with _pool.acquire() as conn, conn.transaction():
        await conn.execute("DELETE FROM auth_tokens WHERE expires_at <= now()")
        await conn.execute(
            "INSERT INTO auth_tokens (token_hash, user_id, expires_at) "
            "VALUES ($1, $2, now() + make_interval(days => $3))",
            token_hash, user_id, ttl_days,
        )


async def get_user_by_token(token_hash: str) -> Dict[str, Any] | None:
    row = await _pool.fetchrow(f"""
        SELECT {USER_COLUMNS} FROM auth_tokens t JOIN users u ON u.id = t.user_id
        WHERE t.token_hash = $1 AND t.expires_at > now()
    """, token_hash)
    return dict(row) if row else None


async def delete_token(token_hash: str):
    await _pool.execute("DELETE FROM auth_tokens WHERE token_hash = $1", token_hash)


# ─── Conversations ──────────────────────────────────────────────────────────
# Une session qui appartient à un autre utilisateur est traitée comme inexistante.

class SessionOwnershipError(Exception):
    """L'identifiant de session est déjà utilisé par un autre utilisateur."""


# Longueur du titre d'une session, tiré de sa première question.
TITLE_LENGTH = 60


async def session_belongs_to_other(session_id: str, user_id: int) -> bool:
    owner = await _pool.fetchval("SELECT user_id FROM sessions WHERE id = $1", session_id)
    return owner is not None and owner != user_id


async def save_exchange(user_id: int, session_id: str, prompt: str, answer: str):
    """
    Enregistre un tour complet (question + réponse) dans une seule transaction.
    La session est créée au premier échange, avec sa question pour titre.
    """
    title = " ".join(prompt.split())
    if len(title) > TITLE_LENGTH:
        title = title[:TITLE_LENGTH - 1].rstrip() + "…"
    async with _pool.acquire() as conn, conn.transaction():
        await conn.execute(
            "INSERT INTO sessions (id, user_id, title) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
            session_id, user_id, title,
        )
        owner = await conn.fetchval(
            "UPDATE sessions SET updated_at = now() WHERE id = $1 RETURNING user_id", session_id
        )
        if owner != user_id:
            raise SessionOwnershipError(session_id)
        await conn.executemany(
            "INSERT INTO messages (session_id, role, content) VALUES ($1, $2, $3)",
            [(session_id, "user", prompt), (session_id, "assistant", answer)],
        )


async def get_chat_context(session_id: str, user_id: int) -> Tuple[str | None, List[Dict[str, Any]]]:
    """
    Résumé de la session et messages qu'il ne couvre pas encore (avec leur id),
    du plus ancien au plus récent.
    """
    async with _pool.acquire() as conn, conn.transaction(isolation="repeatable_read", readonly=True):
        session = await conn.fetchrow(
            "SELECT summary, summary_upto FROM sessions WHERE id = $1 AND user_id = $2", session_id, user_id
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


async def list_sessions(user_id: int) -> List[Dict[str, Any]]:
    rows = await _pool.fetch(
        "SELECT id, title, created_at, updated_at FROM sessions WHERE user_id = $1 ORDER BY updated_at DESC",
        user_id,
    )
    return [dict(row) for row in rows]


async def get_messages(session_id: str, user_id: int) -> List[Dict[str, Any]] | None:
    """Tous les messages bruts de la session (le résumé ne sert qu'au LLM), ou None."""
    async with _pool.acquire() as conn, conn.transaction(isolation="repeatable_read", readonly=True):
        if not await conn.fetchval(
            "SELECT 1 FROM sessions WHERE id = $1 AND user_id = $2", session_id, user_id
        ):
            return None
        rows = await conn.fetch(
            "SELECT role, content, created_at FROM messages WHERE session_id = $1 ORDER BY id ASC", session_id
        )
    return [dict(row) for row in rows]


async def delete_session(session_id: str, user_id: int) -> bool:
    """Supprime la session et ses messages (ON DELETE CASCADE)."""
    status = await _pool.execute("DELETE FROM sessions WHERE id = $1 AND user_id = $2", session_id, user_id)
    return status != "DELETE 0"


# ─── Documents (RAG) ────────────────────────────────────────────────────────
# Documents de référence communs à tous les utilisateurs, indexés par l'admin
# (python main.py index <fichier>).

async def find_document_by_hash(sha256: str) -> Dict[str, Any] | None:
    row = await _pool.fetchrow("SELECT id, source FROM documents WHERE sha256 = $1", sha256)
    return dict(row) if row else None


async def insert_document(
    source: str, sha256: str, chunks: List[str], embeddings: List[List[float]]
) -> Dict[str, Any]:
    """Lève asyncpg.UniqueViolationError si un document de même empreinte existe déjà."""
    async with _pool.acquire() as conn, conn.transaction():
        row = await conn.fetchrow(
            "INSERT INTO documents (source, sha256) VALUES ($1, $2) RETURNING id, source, created_at",
            source, sha256,
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
