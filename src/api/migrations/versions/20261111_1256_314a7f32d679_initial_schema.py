"""initial schema

Revision ID: 314a7f32d679
Revises:
Create Date: 2026-11-11 12:56:32+00:00

Schéma de départ de Jaden : comptes et jetons de connexion, conversations
(avec leur résumé glissant) et documents de référence du RAG (passages
vectorisés + tsvector pour BM25).
"""
from typing import Sequence, Union

from alembic import op
from config import EMBEDDING_DIM

revision: str = "314a7f32d679"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute("""
        CREATE TABLE users (
            id BIGSERIAL PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            is_admin BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    # Seule l'empreinte SHA-256 du jeton est stockée : une fuite de la base ne
    # donne pas de jeton utilisable.
    op.execute("""
        CREATE TABLE auth_tokens (
            token_hash TEXT PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            expires_at TIMESTAMPTZ NOT NULL
        )
    """)
    op.execute("CREATE INDEX auth_tokens_user_id_idx ON auth_tokens (user_id)")

    # Résumé glissant : summary remplace les messages d'id <= summary_upto dans le contexte du LLM.
    op.execute("""
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title TEXT,
            summary TEXT,
            summary_upto BIGINT NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX sessions_user_updated_idx ON sessions (user_id, updated_at DESC)")

    # Uniquement les tours de conversation (user / assistant).
    op.execute("""
        CREATE TABLE messages (
            id BIGSERIAL PRIMARY KEY,
            session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX messages_session_id_idx ON messages (session_id, id)")

    # sha256 : empreinte du fichier, pour refuser un document déjà indexé.
    op.execute("""
        CREATE TABLE documents (
            id BIGSERIAL PRIMARY KEY,
            source TEXT NOT NULL,
            sha256 TEXT NOT NULL UNIQUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    # La dimension est figée à la création : init_db vérifie ensuite qu'elle
    # correspond à EMBEDDING_DIM. La configuration du tsvector doit rester celle
    # de search_chunks_bm25 (database.py).
    op.execute(f"""
        CREATE TABLE chunks (
            id BIGSERIAL PRIMARY KEY,
            document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            position INT NOT NULL,
            content TEXT NOT NULL,
            embedding vector({EMBEDDING_DIM}) NOT NULL,
            tsv tsvector GENERATED ALWAYS AS (to_tsvector('french', content)) STORED
        )
    """)
    op.execute("CREATE INDEX chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops)")
    op.execute("CREATE INDEX chunks_tsv_idx ON chunks USING gin (tsv)")
    op.execute("CREATE INDEX chunks_document_id_idx ON chunks (document_id)")


def downgrade() -> None:
    # Supprime toutes les données. L'extension vector est laissée en place.
    op.execute("DROP TABLE IF EXISTS chunks, documents, messages, sessions, auth_tokens, users")
