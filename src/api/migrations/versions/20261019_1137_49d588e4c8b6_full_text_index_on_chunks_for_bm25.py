"""full-text index on chunks for BM25

Revision ID: 49d588e4c8b6
Revises: 3fd7898783fa
Create Date: 2026-10-19 11:37:44.713476+00:00

Ajoute aux passages leur tsvector (configuration french : minuscules, accents
conservés, mots vides retirés, racinisation) et un index GIN, pour la partie
lexicale (BM25) de la recherche hybride. La colonne étant générée, les passages
existants sont indexés par la migration elle-même.
"""
from typing import Sequence, Union

from alembic import op

revision: str = '49d588e4c8b6'
down_revision: Union[str, Sequence[str], None] = '3fd7898783fa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # La configuration doit rester celle de search_chunks_bm25 (database.py).
    op.execute("""
        ALTER TABLE chunks
        ADD COLUMN tsv tsvector GENERATED ALWAYS AS (to_tsvector('french', content)) STORED
    """)
    op.execute("CREATE INDEX chunks_tsv_idx ON chunks USING gin (tsv)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS chunks_tsv_idx")
    op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS tsv")
