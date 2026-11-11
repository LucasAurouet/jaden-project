"""english full-text on chunks

Revision ID: a9b3822bfe8b
Revises: ac6a3c1d5424
Create Date: 2026-11-11 13:41:23+00:00

Jaden ne gère que l'anglais : le tsvector des passages (partie BM25 de la
recherche hybride du RAG) passe de la configuration french à english. La
colonne étant générée, les passages existants sont réindexés par la migration.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a9b3822bfe8b"
down_revision: Union[str, Sequence[str], None] = "ac6a3c1d5424"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _set_config(config: str) -> None:
    # La configuration doit rester celle de search_chunks_bm25 (database.py).
    op.execute("ALTER TABLE chunks DROP COLUMN tsv")
    op.execute(f"ALTER TABLE chunks ADD COLUMN tsv tsvector GENERATED ALWAYS AS (to_tsvector('{config}', content)) STORED")
    op.execute("CREATE INDEX chunks_tsv_idx ON chunks USING gin (tsv)")


def upgrade() -> None:
    _set_config("english")


def downgrade() -> None:
    _set_config("french")
