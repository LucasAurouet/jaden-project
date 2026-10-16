"""initial schema

Revision ID: 3fd7898783fa
Revises:
Create Date: 2026-10-16 15:18:33.524964+00:00

Reprend le schéma qu'init_db créait avant Alembic. Tout est en IF NOT EXISTS :
une base existante adopte cette révision sans perdre ses données, et les
colonnes de résumé sont ajoutées aux bases antérieures au résumé glissant.
"""
from typing import Sequence, Union

from alembic import op
from config import EMBEDDING_DIM

revision: str = "3fd7898783fa"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            title TEXT DEFAULT 'Nouvelle discussion',
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """)
    # Résumé glissant : remplace les messages d'id <= summary_upto dans le contexte du LLM.
    op.execute("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS summary TEXT")
    op.execute("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS summary_upto BIGINT NOT NULL DEFAULT 0")

    # Uniquement les tours de conversation (user / assistant).
    op.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id BIGSERIAL PRIMARY KEY,
            session_id TEXT REFERENCES sessions(id) ON DELETE CASCADE,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id BIGSERIAL PRIMARY KEY,
            source TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """)

    # La dimension est figée à la création : init_db vérifie ensuite qu'elle correspond à EMBEDDING_DIM.
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS chunks (
            id BIGSERIAL PRIMARY KEY,
            document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            position INT NOT NULL,
            content TEXT NOT NULL,
            embedding vector({EMBEDDING_DIM}) NOT NULL
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    # Supprime toutes les données. L'extension vector est laissée en place.
    op.execute("DROP TABLE IF EXISTS chunks, documents, messages, sessions")
